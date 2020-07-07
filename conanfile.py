from conans import ConanFile
import os
import re
import sys


class AndroidNdkConan(ConanFile):
    name = "android_ndk"
    version = "0.1"
    settings = {"os_build": ["Windows", "Linux", "Macos"],
                "arch_build": ["x86", "x86_64"]}
    settings_target = {"compiler": ["clang"],
                       "os": ["Android"],
                       "arch": ["x86", "x86_64", "armv7", "armv8"]}
    options = {"NDKRootPath": "ANY"}
    default_options = {"NDKRootPath": None}

    _ndk_root = None
    no_copy_source = True
    exports_sources = ["WrappedToolchain.cmake.in"]

    @property
    def _arch(self):
        return self.settings_target.arch if self.settings_target is not None else self.settings.arch

    @property
    def _api_level(self):
        return self.settings_target.os.api_level if self.settings_target is not None else self.settings.os.api_level

    @property
    def _ndk_home(self):
        return str(self.options.NDKRootPath) or self.env.get(
            "ANDROID_NDK_HOME", None) or os.environ["ANDROID_NDK_HOME"]

    @property
    def _platform(self):
        return {"Windows": "windows",
                "Macos": "darwin",
                "Linux": "linux"}.get(str(self.settings.os_build))

    @property
    def _android_abi(self):
        return {"x86": "x86",
                "x86_64": "x86_64",
                "armv7": "armeabi-v7a",
                "armv8": "arm64-v8a"}.get(str(self._arch))

    @property
    def _llvm_triplet(self):
        arch = {'armv7': 'arm',
                'armv8': 'aarch64',
                'x86': 'i686',
                'x86_64': 'x86_64'}.get(str(self._arch))
        abi = 'androideabi' if self._arch == 'armv7' else 'android'
        return '%s-linux-%s' % (arch, abi)

    @property
    def _clang_triplet(self):
        arch = {'armv7': 'armv7a',
                'armv8': 'aarch64',
                'x86': 'i686',
                'x86_64': 'x86_64'}.get(str(self._arch))
        abi = 'androideabi' if self._arch == 'armv7' else 'android'
        return '%s-linux-%s' % (arch, abi)

    @property
    def _host(self):
        return self._platform if self.settings.arch_build == "x86" else self._platform + "-x86_64"

    def _tool_name(self, tool):
        if 'clang' in tool:
            suffix = '.cmd' if self.settings.os_build == 'Windows' else ''
            return '%s%s-%s%s' % (self._clang_triplet, self._api_level, tool, suffix)
        else:
            suffix = '.exe' if self.settings.os_build == 'Windows' else ''
            return '%s-%s%s' % (self._llvm_triplet, tool, suffix)

    def _define_tool_var(self, name, value):
        ndk_bin = os.path.join(self._ndk_root, 'bin')
        path = os.path.join(ndk_bin, self._tool_name(value))
        self.output.info('Creating %s environment variable: %s' % (name, path))
        return path

    def package(self):
        with open(os.path.join(self.source_folder, "WrappedToolchain.cmake.in")) as template_file:
            with open(os.path.join(self.package_folder, "WrappedToolchain.cmake"), "w") as toolchain_file:
                for line in template_file.readlines():
                    toolchain_file.write(line.replace("@ANDROID_NDK_HOME@", self._ndk_home))

    def package_info(self):
        ndk_home = self._ndk_home
        self.output.info(f"ndk_home is {ndk_home}")

        revision_pattern = re.compile("Pkg.Revision = (.+)")
        try:
            ndk_revision = None
            with open(os.path.join(ndk_home, "source.properties")) as source:
                for line in source.readlines():
                    match = revision_pattern.match(line)
                    if match is not None:
                        ndk_revision = match.group(1)
            if ndk_revision is not None:
                self.output.info(
                    "Detected ndk revision is {}".format(ndk_revision))
                self.user_info.ndk_revision = ndk_revision
            else:
                raise RuntimeError("Cannot find revision")
        except Exception as e:
            raise RuntimeError(f"Cannot determine ndk revision: {e}")

        self.env_info.NDK_HOME = ndk_home
        self._ndk_root = os.path.join(
            ndk_home, "toolchains", "llvm", "prebuilt", self._host)
        self.env_info.NDK_ROOT = self._ndk_root
        self.env_info.CHOST = self._llvm_triplet
        sysroot = os.path.join(self._ndk_root, 'sysroot')
        self.env_info.SYSROOT = sysroot
        self.cpp_info.sysroot = sysroot

        self.env_info.CONAN_CMAKE_TOOLCHAIN_FILE = os.path.join(
            self.package_folder, "WrappedToolchain.cmake")
        self.env_info.ANDROID_NATIVE_API_LEVEL = str(
            self._api_level)
        self.env_info.ANDROID_TOOLCHAIN = "clang"
        self.env_info.ANDROID_ABI = self._android_abi
        self.env_info.ANDROID_STL = str(
            self.settings_target.compiler.libcxx if self.settings_target is not None else self.settings.compiler.libcxx)
        self.env_info.CMAKE_FIND_ROOT_PATH = sysroot
        self.env_info.CMAKE_FIND_ROOT_PATH_MODE_PROGRAM = "BOTH"
        self.env_info.CMAKE_FIND_ROOT_PATH_MODE_LIBRARY = "BOTH"
        self.env_info.CMAKE_FIND_ROOT_PATH_MODE_INCLUDE = "BOTH"
        self.env_info.CMAKE_FIND_ROOT_PATH_MODE_PACKAGE = "BOTH"

        self.env_info.CC = self._define_tool_var('CC', 'clang')
        self.env_info.CXX = self._define_tool_var('CXX', 'clang++')
        self.env_info.LD = self._define_tool_var('LD', 'ld')
        self.env_info.AR = self._define_tool_var('AR', 'ar')
        self.env_info.AS = self._define_tool_var('AS', 'as')
        self.env_info.RANLIB = self._define_tool_var('RANLIB', 'ranlib')
        self.env_info.STRIP = self._define_tool_var('STRIP', 'strip')
        self.env_info.ADDR2LINE = self._define_tool_var(
            'ADDR2LINE', 'addr2line')
        self.env_info.NM = self._define_tool_var('NM', 'nm')
        self.env_info.OBJCOPY = self._define_tool_var('OBJCOPY', 'objcopy')
        self.env_info.OBJDUMP = self._define_tool_var('OBJDUMP', 'objdump')
        self.env_info.READELF = self._define_tool_var('READELF', 'readelf')
        self.env_info.ELFEDIT = self._define_tool_var('ELFEDIT', 'elfedit')
