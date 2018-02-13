import re, os, sys, shutil
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
    )
    options = {
        'shared': [True, False],
    }
    default_options = ('shared=True')

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

    def configure(self):
        self.options['boost'].shared = self.options.shared
        self.options['gtest'].shared = self.options.shared
        self.options['qhull'].shared = self.options.shared
        self.options['vtk'].shared = self.options.shared

        if self.options.shared and self.settings.os == 'Windows' and self.version == '1.8.1':
            self.options['flann'].shared = self.options.shared

    def build(self):

        vtk_major = '.'.join(self.deps_cpp_info['vtk'].version.split('.')[:2])

        # TODO See if we can use self.deps_cpp_info['vtk'].res
        vtk_cmake_rel_dir = f'lib/cmake/vtk-{vtk_major}'
        vtk_cmake_dir = f'{self.deps_cpp_info["vtk"].rootpath}/{vtk_cmake_rel_dir}'

        args = []
        if self.options.shared:
            args.append('-DBUILD_SHARED_LIBS=ON')
        args.append('-DCMAKE_CXX_FLAGS=-mtune=generic')
        args.append('-DBOOST_ROOT:PATH=%s'%self.deps_cpp_info['boost'].rootpath)

        libqhull = None
        for l in self.deps_cpp_info['qhull'].libs:
            if re.search(r'qhull\d?', l):
                libqhull = l
                break
        if libqhull is None:
            self.output.error('Could not find QHULL library')
            sys.exit(-1)


        args.append('-DQHULL_INCLUDE_DIR:PATH=%s'%os.path.join(self.deps_cpp_info['qhull'].rootpath, self.deps_cpp_info['qhull'].includedirs[0]))
        args.append('-DQHULL_LIBRARY:FILEPATH=%s'%os.path.join(self.deps_cpp_info['qhull'].rootpath, self.deps_cpp_info['qhull'].libdirs[0], libqhull))

        args.append('-DQt5Core_DIR:PATH=%s'%     os.path.join(self.deps_cpp_info['qt'].rootpath, 'lib', 'cmake', 'Qt5Core'))
        args.append('-DQt5_DIR:PATH=%s'%         os.path.join(self.deps_cpp_info['qt'].rootpath, 'lib', 'cmake', 'Qt5'))
        args.append('-DQt5Gui_DIR:PATH=%s'%      os.path.join(self.deps_cpp_info['qt'].rootpath, 'lib', 'cmake', 'Qt5Gui'))
        args.append('-DQt5OpenGL_DIR:PATH=%s'%   os.path.join(self.deps_cpp_info['qt'].rootpath, 'lib', 'cmake', 'Qt5OpenGL'))
        args.append('-DQt5Widgets_DIR:PATH=%s'%  os.path.join(self.deps_cpp_info['qt'].rootpath, 'lib', 'cmake', 'Qt5Widgets'))

        args.append('-DGTEST_ROOT:PATH=%s'%self.deps_cpp_info['gtest'].rootpath)
        args.append(f'-DVTK_DIR:PATH={vtk_cmake_dir}')
        args.append('-DBUILD_surface_on_nurbs:BOOL=ON')

        # Despite provided this with pkg-config, and 1.7.2 finding these
        # successfully with pkg-config, cmake evidentally still requires
        # EIGEN_INCLUDE_DIR ... *shrugs*
        args.append('-DEIGEN_INCLUDE_DIR:PATH=%s'%os.path.join(self.deps_cpp_info['eigen'].rootpath, 'include', 'eigen3'))

        pkg_vars = {
            'PKG_CONFIG_eigen3_PREFIX': self.deps_cpp_info['eigen'].rootpath,
            'PKG_CONFIG_flann_PREFIX':  self.deps_cpp_info['flann'].rootpath,
            'PKG_CONFIG_PATH': ':'.join([
                os.path.join(self.deps_cpp_info['eigen'].rootpath, 'share', 'pkgconfig'),
                os.path.join(self.deps_cpp_info['flann'].rootpath, 'lib', 'pkgconfig'),
            ])
        }

        cmake = CMake(self)
        with tools.environment_append(pkg_vars):
            cmake.configure(source_folder=self.name, args=args)
            cmake.build()

        cmake.install()

        # Fix up the CMake Find Script PCL generated
        self.output.info('Inserting Conan variables in to the PCL CMake Find script.')
        self.fixFindPackage(cmake.build_folder, vtk_cmake_rel_dir)

    def fixFindPackage(self, path, vtk_cmake_rel_dir):
        """
        Insert some variables into the PCL find script generated in the
        build so that we can use it in our CMake scripts
        """

        # Now, run some regex's through the
        with open(f'{path}/PCLConfig.cmake') as f:
            data = f.read()

        sub_map = {
            'eigen': os.path.join('${CONAN_INCLUDE_DIRS_EIGEN}', 'eigen3'),
            'boost': '${CONAN_INCLUDE_DIRS_BOOST}',
            'flann': '${CONAN_INCLUDE_DIRS_FLANN}',
            'qhull': '${CONAN_INCLUDE_DIRS_QHULL}',
            'vtk':   os.path.join('${CONAN_VTK_ROOT}', vtk_cmake_rel_dir),
            'pcl':   os.path.join('${CONAN_PCL_ROOT}', 'pcl')
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

        outp = open(f'{path}/PCLConfig.cmake', 'w')
        outp.write(data)

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

        # Populate the libs.  Manually written.  Not sure how I could populate
        # this automatically yet.
        libs = [
            'pcl_common',
            'pcl_features',
            'pcl_filters',
            'pcl_io',
            'pcl_io_ply',
            'pcl_kdtree',
            'pcl_keypoints',
            'pcl_octree',
            'pcl_outofcore',
            'pcl_people',
            'pcl_recognition',
            'pcl_registration',
            'pcl_sample_consensus',
            'pcl_search',
            'pcl_segmentation',
            'pcl_surface',
            'pcl_tracking',
            'pcl_visualization',
        ]
        if pcl_major >= 8:
            libs += ['pcl_stereo', 'pcl_ml']

        if 'Linux' == self.settings.os:
            prefix = 'lib'
            suffix = 'so' if self.options.shared else 'a'
        else:
            prefix = ''
            suffix = 'lib'

        if self.settings.os == "Linux":
            self.cpp_info.libs = list(map((lambda name: f'{prefix}{name}.{suffix}'), libs))
        else:
            build_type = self.settings.build_type.lower()
            self.cpp_info.libs = list(map((lambda name: f'{prefix}{name}_{build_type}.{suffix}'), libs))
            self.cpp_info.libs = list(map((lambda name: name + '_release.dll'), libs))

# vim: ts=4 sw=4 expandtab ffs=unix ft=python foldmethod=marker :
