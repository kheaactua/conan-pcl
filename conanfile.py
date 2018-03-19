import re, os, shutil
from conans import ConanFile, CMake, tools


class PclConan(ConanFile):
    """ Tested with versions 1.7.2, 1.8.0, and 1.8.1 """

    name         = 'pcl'
    license      = 'BSD'
    url          = 'http://docs.pointclouds.org/'
    description  = 'Point cloud library'
    settings     = 'os', 'compiler', 'build_type', 'arch'
    build_policy = 'missing'
    generators   = 'cmake'
    requires = (
        'boost/[>1.46]@ntc/stable',
        'eigen/[>=3.2.0]@ntc/stable',
        'flann/[>=1.6.8]@ntc/stable',
        'qhull/2015.2@ntc/stable',
        'vtk/[>=5.6.1]@ntc/stable',
        'qt/[>=5.3.2]@ntc/stable',
        'gtest/[>=1.8.0]@lasote/stable',
        'helpers/[>=0.1]@ntc/stable',
    )
    build_requires = 'pkg-config/0.29.2@ntc/stable'

    options         = {
        'shared': [True, False],
        'fPIC':   [True, False],
        'cxx11':  [True, False],
    }
    default_options = ('shared=True', 'fPIC=True', 'cxx11=True')

    def config_options(self):
        """ First configuration step. Only settings are defined. Options can be removed
        according to these settings
        """
        if self.settings.compiler == "Visual Studio":
            self.options.remove("fPIC")

    def configure(self):
        self.options['boost'].shared = self.options.shared
        if self.settings.compiler != "Visual Studio":
            self.options['boost'].fPIC = True
        self.options['gtest'].shared = self.options.shared

        self.options['qhull'].cxx11  = self.options.cxx11

        self.options['vtk'].shared = self.options.shared

        # I don't remember why this 'constraint' is here
        if self.options.shared and self.settings.os == 'Windows' and self.version == '1.8.4':
            self.options['flann'].shared = self.options.shared
        self.options['flann'].cxx11 = self.options.cxx11

    def source(self):

        hashes = {
            '1.8.1': '436704215670bb869ca742af48c749a9',
            '1.8.0': '8c1308be2c13106e237e4a4204a32cca',
            '1.7.2': '02c72eb6760fcb1f2e359ad8871b9968',
        }

        if self.version in hashes:
            archive = f'pcl-{self.version}.tar.gz'
            if os.path.exists(os.path.join('/tmp', archive)):
                shutil.copy(os.path.join('/tmp', archive), self.source_folder)
            else:
                tools.download(
                    url=f'https://github.com/PointCloudLibrary/pcl/archive/{archive}',
                    filename=archive
                )
                tools.check_md5(archive, hashes[self.version])
                tools.unzip(archive)
                shutil.move(f'pcl-pcl-{self.version}', self.name)
        else:
            self.run(f'git clone https://github.com/PointCloudLibrary/pcl.git {self.name}')
            self.run(f'cd {self.name} && git checkout pcl-{self.version}')

        if self.settings.compiler == 'gcc':
            import cmake_helpers
            cmake_helpers.wrapCMakeFile(os.path.join(self.source_folder, self.name), output_func=self.output.info)

    def build(self):

        vtk_major = '.'.join(self.deps_cpp_info['vtk'].version.split('.')[:2])

        # TODO See if we can use self.deps_cpp_info['vtk'].res
        vtk_cmake_rel_dir = f'lib/cmake/vtk-{vtk_major}'
        vtk_cmake_dir = f'{self.deps_cpp_info["vtk"].rootpath}/{vtk_cmake_rel_dir}'

        def tweakPath(path):
            # CMake and pkg-config like forward slashes, hopefully there are no
            # spaces or any other character like that
            if 'Windows' == self.settings.os:
                return re.sub(r'\\', r'/', path)
            else:
                return path

        # Create our CMake generator
        cmake = CMake(self)

        # Boost
        cmake.definitions['BOOST_ROOT:PATH'] = tweakPath(self.deps_cpp_info['boost'].rootpath)


        if 'fPIC' in self.options and self.options.fPIC:
            cmake.definitions['CMAKE_POSITION_INDEPENDENT_CODE'] = 'ON'
        if self.options.cxx11:
            cmake.definitions['CMAKE_CXX_STANDARD'] = 11

        cxx_flags = []
        if self.settings.compiler in ['gcc']:
            cxx_flags.append('-mtune=generic')
            cxx_flags.append('-frecord-gcc-switches')

        if len(cxx_flags):
            cmake.definitions['ADDITIONAL_CXX_FLAGS:STRING'] = ' '.join(cxx_flags)

        cmake.definitions['QHULL_ROOT:PATH']     = tweakPath(os.path.join(self.deps_cpp_info['qhull'].rootpath))

        # GTest
        cmake.definitions['GTEST_ROOT:PATH']             = self.deps_cpp_info['gtest'].rootpath

        # VTK
        cmake.definitions['VTK_DIR:PATH']                = vtk_cmake_dir

        # PCL Options
        cmake.definitions['BUILD_surface_on_nurbs:BOOL'] = 'ON'
        cmake.definitions['BUILD_SHARED_LIBS:BOOL'] = 'ON' if self.options.shared else 'OFF'
        if 'Windows' == self.settings.os:
            cmake.definitions['PCL_BUILD_WITH_BOOST_DYNAMIC_LINKING_WIN32:BOOL'] = 'ON' if self.options['boost'].shared else 'OFF'

        # Qt
        # Qt exposes pkg-config files (at least on Linux, on Windows there are
        # .prl files *shrugs*, but PCL (pcl_find_qt5.cmake) doesn't use this.
        for p in ['Core', 'Gui', 'OpenGL', 'Widgets']:
            cmake.definitions[f'Qt5{p}_DIR:PATH'] = tweakPath(os.path.join(self.deps_cpp_info['qt'].rootpath, 'lib', 'cmake', f'Qt5{p}'))
        cmake.definitions['QT_QMAKE_EXECUTABLE:PATH'] = tweakPath(os.path.join(self.deps_cpp_info['qt'].rootpath, 'bin', 'qmake'))

        pkg_vars = {}
        pkg_config_path = []

        # Eigen
        pkg_vars['PKG_CONFIG_eigen3_PREFIX'] = tweakPath(self.deps_cpp_info['eigen'].rootpath)
        pkg_config_path.append(os.path.join(self.deps_cpp_info['eigen'].rootpath, 'share', 'pkgconfig'))
        # Despite provided this with pkg-config, and 1.7.2 finding these
        # successfully with pkg-config, cmake evidentially still requires
        # EIGEN_INCLUDE_DIR ... *shrugs*
        cmake.definitions['EIGEN_INCLUDE_DIR:PATH'] = tweakPath(os.path.join(self.deps_cpp_info['eigen'].rootpath, 'include', 'eigen3'))

        # Flann
        pkg_vars['PKG_CONFIG_flann_PREFIX']  = tweakPath(self.deps_cpp_info['flann'].rootpath)
        pkg_config_path.append(os.path.join(self.deps_cpp_info['flann'].rootpath, 'lib', 'pkgconfig'))

        pkg_vars['PKG_CONFIG_PATH'] = (';' if 'Windows' == self.settings.os else ':').join(
            list(map(lambda p: tweakPath(p), pkg_config_path))
        )


        # Debug
        s = '\nEnvironment:\n'
        for k,v in pkg_vars.items():
            s += ' - %s=%s\n'%(k, v)
        self.output.info(s)
        s = '\nCMake Definitions:\n'
        for k,v in cmake.definitions.items():
            s += ' - %s=%s\n'%(k, v)
        self.output.info(s)

        with tools.environment_append(pkg_vars):
            cmake.configure(source_folder=self.name)
            cmake.build()

        cmake.install()

        # Fix up the CMake Find Script PCL generated
        # TODO Look into experimental tools.patch_fongi_paths() function
        self.output.info('Inserting Conan variables in to the PCL CMake Find script.')
        self.fixFindPackage(cmake.build_folder, vtk_cmake_rel_dir)

    def fixFindPackage(self, path, vtk_cmake_rel_dir):
        """
        Insert some variables into the PCL find script generated in the
        build so that we can use it in our CMake scripts

        TODO consider/experiment using CMake.patch_config_paths http://docs.conan.io/en/latest/reference/build_helpers/cmake.html
        """

        # Now, run some regex's through the
        with open(f'{path}/PCLConfig.cmake') as f: data = f.read()

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

        with open(f'{path}/PCLConfig.cmake', 'w') as f: f.write(data)

    def package(self):
        pass

    def package_info(self):
        # PCL has a find script which populates variables holding include paths
        # and libs, but since it doesn't define a target, and re-searches for
        # Eigen and other dependencies, it's a little annoying to use - still,
        # it's available by adding the resdir (below) to the CMAKE_MODULE_DIR
        #
        # While this might break encapsulation a little, we will add the libs
        # to the package info such that we can simply use the conan package if
        # we wish.

        (pcl_release, pcl_major, pcl_minor) = [int(i) for i in self.version.split('.')]
        pcl_version_str = f'{pcl_release}.{pcl_major}'

        # Add the directory with CMake.. Not sure if this is a good use of resdirs
        self.cpp_info.resdirs = [os.path.join('share', f'pcl-{pcl_version_str}')]

        # Add the real include path, the default one points to include/ but the one
        # we use is include/pcl-1.8
        self.cpp_info.includedirs = [os.path.join('include', f'pcl-{pcl_version_str}')]

        # Populate the libs
        self.cpp_info.libs = tools.collect_libs(self)

        if self.options.shared and 'Windows' == self.settings.os:
            # Add our libs to PATH
            self.env_info.path.append(os.path.join(self.package_folder, 'lib'))

# vim: ts=4 sw=4 expandtab ffs=unix ft=python foldmethod=marker :
