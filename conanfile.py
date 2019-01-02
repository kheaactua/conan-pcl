#!/usr/bin/env python
# -*- coding: future_fstrings -*-
# -*- coding: utf-8 -*-

import re, os, shutil, glob
from conans import ConanFile, CMake, tools
from conans.model.version import Version
from conans.errors import ConanException

class ansi:
	green  = u'\033[32m'
	yellow = u'\033[33m'
	clear  = u'\033[0m'

class PclConan(ConanFile):
    name         = 'pcl'
    version      = '1.9.1'
    md5_hash     = '4d4cfb6bf87cc1f08703deeeac1eb6e2'
    license      = 'MIT'
    url          = 'https://github.com/kheaactua/conan-pcl'
    description  = 'Point cloud library'
    settings     = 'os', 'compiler', 'build_type', 'arch'
    exports      = 'patches/*'
    requires     = (
        'boost/[>1.46]@ntc/stable',
        'eigen/[>=3.2.0]@ntc/stable',
        'flann/[>=1.6.8]@ntc/stable',
        'qhull/2015.2@ntc/stable',
        'vtk/[>=5.6.1]@ntc/stable',
        'gtest/[>=1.8.0]@bincrafters/stable',
        'zlib/[>=1.2.11]@conan/stable',
        'helpers/[>=0.3]@ntc/stable',
    )

    options      = {
        'shared':  [True, False],
        'fPIC':    [True, False],
        'cxx11':   [True, False],
        'with_qt': [True, False],
    }
    default_options = ('shared=True', 'fPIC=True', 'cxx11=True', 'with_qt=True')

    def config_options(self):
        if 'Visual Studio' == self.settings.compiler:
            self.options.remove('fPIC')

    def requirements(self):
        if self.options.with_qt:
            self.requires('qt/[>=5.3.2]@ntc/stable')

    def source(self):
        try:
            archive = f'pcl-{self.version}.tar.gz'
            if not os.path.exists(archive):
                # Sometimes the file can already exist
                tools.download(
                    url=f'https://github.com/PointCloudLibrary/pcl/archive/{archive}',
                    filename=archive
                )
                tools.check_md5(archive, self.md5_hash)
            tools.unzip(archive)
            shutil.move(f'pcl-pcl-{self.version}', self.name)
        except ConanException as e:
            self.output.warn('Received exception while downloding PCL archive.  Attempting to clone from source. Exception = %s'%e)
            g = tools.Git(folder=self.name)
            g.clone('https://github.com/PointCloudLibrary/pcl.git', branch='pcl-%s'%self.version)

        # Overload the top CMakeLists file so that we can inject in some
        # definitions, or append to the CXX_FLAGS
        import cmake_helpers
        cmake_helpers.wrapCMakeFile(
            source_folder=os.path.join(self.source_folder, self.name),
            output_func=self.output.info,
        )

        patch_files = glob.glob('patches/*')
        for patch_file in patch_files:
            self.output.info(f'Applying patch {patch_file}')
            tools.patch(patch_file=patch_file, base_path='pcl')

        # In boost 1.66, sha1.hpp got moved (but there was a patch), in 1.68,
        # the patch got removed too.
        if Version(self.deps_cpp_info['boost'].version) >= '1.66':
            tools.replace_path_in_file(
                file_path=os.path.join(self.name, 'visualization', 'src', 'pcl_visualizer.cpp'),
                search='boost/uuid/sha1.hpp',
                replace='boost/uuid/detail/sha1.hpp',
                windows_paths=False,
            )

    def _set_up_cmake(self):
        """
        Set up the CMake generator so that it can be used in build() and package()
        """

        # Import from helpers/x@ntc/stable
        from platform_helpers import adjustPath

        vtk_major = '.'.join(self.deps_cpp_info['vtk'].version.split('.')[:2])

        # TODO See if we can use self.deps_cpp_info['vtk'].res
        vtk_cmake_rel_dir = f'lib/cmake/vtk-{vtk_major}'
        vtk_cmake_dir = f'{self.deps_cpp_info["vtk"].rootpath}/{vtk_cmake_rel_dir}'

        # Create our CMake generator
        cmake = CMake(self)

        # Boost
        cmake.definitions['BOOST_ROOT:PATH'] = adjustPath(self.deps_cpp_info['boost'].rootpath)

        if 'fPIC' in self.options and self.options.fPIC:
            cmake.definitions['CMAKE_POSITION_INDEPENDENT_CODE:BOOL'] = 'ON'
        if self.options.cxx11:
            cmake.definitions['CMAKE_CXX_STANDARD'] = 11

        cxx_flags = []
        if self.settings.compiler in ['gcc']:
            if not self.settings.get_safe('arch').startswith('arm'):
                cxx_flags.append('-mtune=generic')
            cxx_flags.append('-frecord-gcc-switches')

        # Set a cache variable we created by wrapping the top CMAke file in source()
        if len(cxx_flags):
            cmake.definitions['ADDITIONAL_CXX_FLAGS:STRING'] = ' '.join(cxx_flags)

        if Version(self.deps_cpp_info['boost'].version) >= '1.66':
            cmake.definitions['ADDITIONAL_DEFINITIONS:STRING'] ='-DBOOST_UUID_RANDOM_GENERATOR_COMPAT'

        # QHull
        cmake.definitions['QHULL_ROOT:PATH'] = adjustPath(self.deps_cpp_info['qhull'].rootpath)

        # GTest
        cmake.definitions['GTEST_ROOT:PATH'] = adjustPath(self.deps_cpp_info['gtest'].rootpath)

        # VTK
        cmake.definitions['VTK_DIR:PATH']    = adjustPath(vtk_cmake_dir)

        # PCL Options
        cmake.definitions['BUILD_surface_on_nurbs:BOOL'] = 'ON'
        cmake.definitions['BUILD_SHARED_LIBS:BOOL'] = 'ON' if self.options.shared else 'OFF'
        if tools.os_info.is_windows:
            cmake.definitions['PCL_BUILD_WITH_BOOST_DYNAMIC_LINKING_WIN32:BOOL'] = 'ON' if self.options['boost'].shared else 'OFF'

        if self.options.with_qt:
            # Qt exposes pkg-config files (at least on Linux, on Windows there are
            # .prl files *shrugs*, but PCL (pcl_find_qt5.cmake) doesn't use this.
            qt_deps = ['Core', 'Gui', 'OpenGL', 'Widgets']
            if '7' >= Version(str(self.deps_cpp_info['vtk'].version)):
                qt_deps.append('') # VTK 7 wants Qt5Config (note p='' in Qt5{p}Config)
            for p in qt_deps:
                cmake.definitions[f'Qt5{p}_DIR:PATH'] = adjustPath(os.path.join(self.deps_cpp_info['qt'].rootpath, 'lib', 'cmake', f'Qt5{p}'))
            cmake.definitions['QT_QMAKE_EXECUTABLE:PATH'] = adjustPath(os.path.join(self.deps_cpp_info['qt'].rootpath, 'bin', 'qmake'))

        # Eigen: Despite being provided with pkg-config, and 1.7.2 finding
        # these successfully with pkg-config, cmake evidentially still requires
        # EIGEN_INCLUDE_DIR ... *shrugs*
        cmake.definitions['EIGEN_INCLUDE_DIR:PATH'] = adjustPath(os.path.join(self.deps_cpp_info['eigen'].rootpath, 'include', 'eigen3'))

        # Flann is found via pkg-config

        env_info = {}
        if tools.os_info.is_linux:
            # There's an issue when using boost with shared bzip2 where the shared
            # lib path isn't exposed, and as such PCL can't link.  So here we
            # inject the path into our linker path.
            env_info['LD_LIBRARY_PATH'] = os.path.join(self.deps_cpp_info['bzip2'].rootpath, 'lib')

        return cmake, env_info

    def build(self):

        cmake, env_info = self._set_up_cmake()

        # Debug
        pkg_config_vars = {}
        s = '\nBase Environment:\n'
        for k,v in os.environ.items():
            s += ' - %s=%s\n'%(k, v)
            if 'PKG_CONFIG' in k:
                pkg_config_vars[k] = v
        self.output.info(s)

        if len(env_info.keys()):
            s = '\nAdditional Environment:\n'
            for k,v in env_info.items():
                if 'PKG_CONFIG' in k:
                    if k in os.environ:
                        pkg_config_vars[k] = ansi.red + v + ansi.clear
                    else:
                        pkg_config_vars[k] = v
                s += ' - %s=%s\n'%(k, v)
            self.output.info(s)

        if len(pkg_config_vars):
            s = '\nPkg-Config Specific Environment:\n'
            for k,v in pkg_config_vars.items():
                if k != 'PKG_CONFIG_PATH':
                    s += ' - %s=%s\n'%(k, v)
            if 'PKG_CONFIG_PATH' in pkg_config_vars:
                s += ' - PKG_CONFIG_PATH:\n  - %s'%('\n  - '.join(pkg_config_vars['PKG_CONFIG_PATH'].split(';' if tools.os_info.is_windows else ':')))
            self.output.info(s)

        s = '\nCMake Definitions:\n'
        for k,v in cmake.definitions.items():
            s += ' - %s=%s\n'%(k, v)
        self.output.info(s)

        with tools.environment_append(env_info):
            cmake.configure(source_folder=self.name)
            cmake.build()

    def package(self):
        cmake, env_info = self._set_up_cmake()

        with tools.environment_append(env_info):

            if self.options.with_qt:
                # When cmake is called twice, pcl_find_qt5.cmake for some reason
                # has QT_USE_FILE set to a system path, which fails the
                # configuration.  So this line adjusts it to what it should be by
                # default. (wtf..)
                cmake.definitions['QT_USE_FILE'] = os.path.join(self.build_folder, 'use-qt5.cmake')

            cmake.configure(source_folder=self.name, build_folder=self.build_folder)
            cmake.install()

        # TODO See if we can use self.deps_cpp_info['vtk'].res
        vtk_major = '.'.join(self.deps_cpp_info['vtk'].version.split('.')[:2])
        vtk_cmake_rel_dir = f'lib/cmake/vtk-{vtk_major}'

        # Fix up the CMake Find Script PCL generated
        self.output.info('Inserting Conan variables in to the PCL CMake Find script.')
        self.fixFindPackage(
            src=self.build_folder,
            dst=self.pcl_cmake_dir,
            vtk_cmake_rel_dir=vtk_cmake_rel_dir
        )

    def package_info(self):
        # PCL has a find script which populates variables holding include paths
        # and libs, but since it doesn't define a target, and re-searches for
        # Eigen and other dependencies, it's a little annoying to use - still,
        # it's available by adding the resdir (below) to the CMAKE_MODULE_DIR
        #
        # While this might break encapsulation a little, we will add the libs
        # to the package info such that we can simply use the conan package if
        # we wish.

        (pcl_release, pcl_major) = [int(i) for i in self.version.split('.')[:2]]
        pcl_version_str = f'{pcl_release}.{pcl_major}'

        # Add the directory with CMake.. Not sure if this is a good use of resdirs
        self.cpp_info.resdirs = [self.pcl_cmake_dir]

        # Add the real include path, the default one points to include/ but the one
        # we use is include/pcl-1.8
        self.cpp_info.includedirs = [os.path.join('include', f'pcl-{pcl_version_str}')]

        # Populate the libs
        self.cpp_info.libs = tools.collect_libs(self)

        if self.options.shared and tools.os_info.is_windows:
            # Add our libs to PATH
            self.env_info.path.append(os.path.join(self.package_folder, 'lib'))

        # Populate the pkg-config environment variables
        with tools.pythonpath(self):
            from platform_helpers import adjustPath, appendPkgConfigPath

            self.env_info.PKG_CONFIG_PCL_PREFIX = adjustPath(self.package_folder)
            appendPkgConfigPath(adjustPath(os.path.join(self.package_folder, 'lib', 'pkgconfig')), self.env_info)

    def fixFindPackage(self, src, dst, vtk_cmake_rel_dir):
        """
        Insert some variables into the PCL find script generated in the
        build so that we can use it in our CMake scripts

        TODO consider/experiment using CMake.patch_config_paths http://docs.conan.io/en/latest/reference/build_helpers/cmake.html

        @param src Source folder of PCLConfig.cmake (build directory)
        @param dst Destination for PCLConfig.cmake (package folder)
        """

        self.output.info('Fixing PCLConfig.config found at %s'%src)

        # Now, run some regex's through the
        with open(f'{src}/PCLConfig.cmake') as f: data = f.read()

        sub_map = {
            'eigen': '${CONAN_INCLUDE_DIRS_EIGEN}/eigen3',
            'boost': '${CONAN_INCLUDE_DIRS_BOOST}',
            'flann': '${CONAN_INCLUDE_DIRS_FLANN}',
            'qhull': '${CONAN_INCLUDE_DIRS_QHULL}',
            'vtk':   '${CONAN_VTK_ROOT}/' + vtk_cmake_rel_dir,
            'pcl':   '${CONAN_PCL_ROOT}/pcl'
        }

        # https://regex101.com/r/fZxj7i/1
        regex = r"(?<=\").*?conan.*?(?P<package>(%s)).*?(?=\")"

        for pkg, rep in sub_map.items():
            r = regex%pkg
            m = re.search(r, data)
            if m:
                data = data[0:m.start()] + rep + data[m.end():]
            else:
                self.output.warn('Could not find %s'%pkg)


        self.output.info('Installing fixed PCLConfig.config to %s'%dst)
        if not os.path.exists(os.path.dirname(dst)):
            # Not sure how this could not exist, but just in case..
            os.makedirs(os.path.dirname(dst))

        with open(f'{dst}/PCLConfig.cmake', 'w') as f: f.write(data)

    @property
    def pcl_cmake_dir(self):
        (pcl_release, pcl_major) = [int(i) for i in self.version.split('.')[:2]]
        pcl_version_str = f'{pcl_release}.{pcl_major}'

        if tools.os_info.is_windows:
            # On Windows, this CMake file is in a different place
            d = os.path.join(self.package_folder, 'cmake')
        else:
            d = os.path.join(self.package_folder, 'share', f'pcl-{pcl_version_str}')

        return d

# vim: ts=4 sw=4 expandtab ffs=unix ft=python foldmethod=marker :
