# Copyright 2019 The meson development team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Abstractions for the Intel Compiler families.

Intel provides both a posix/gcc-like compiler (ICC) for MacOS and Linux,
with Meson mixin IntelGnuLikeCompiler.
For Windows, the Intel msvc-like compiler (ICL) Meson mixin
is IntelVisualStudioLikeCompiler.
"""

import os
import typing as T

from ... import mesonlib
from .gnu import GnuLikeCompiler
from .visualstudio import VisualStudioLikeCompiler

if T.TYPE_CHECKING:
    from ...arglist import CompilerArgs
    from ...dependencies import Dependency
    from ...environment import Environment

# XXX: avoid circular dependencies
# TODO: this belongs in a posix compiler class
# NOTE: the default Intel optimization is -O2, unlike GNU which defaults to -O0.
# this can be surprising, particularly for debug builds, so we specify the
# default as -O0.
# https://software.intel.com/en-us/cpp-compiler-developer-guide-and-reference-o
# https://software.intel.com/en-us/cpp-compiler-developer-guide-and-reference-g
# https://software.intel.com/en-us/fortran-compiler-developer-guide-and-reference-o
# https://software.intel.com/en-us/fortran-compiler-developer-guide-and-reference-g
# https://software.intel.com/en-us/fortran-compiler-developer-guide-and-reference-traceback
# https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html


class IntelGnuLikeCompiler(GnuLikeCompiler):
    """
    Tested on linux for ICC 14.0.3, 15.0.6, 16.0.4, 17.0.1, 19.0
    debugoptimized: -g -O2
    release: -O3
    minsize: -O2
    """

    BUILD_ARGS = {
        'plain': [],
        'debug': ["-g", "-traceback"],
        'debugoptimized': ["-g", "-traceback"],
        'release': [],
        'minsize': [],
        'custom': [],
    }  # type: T.Dict[str, T.List[str]]

    OPTIM_ARGS = {
        '0': ['-O0'],
        'g': ['-O0'],
        '1': ['-O1'],
        '2': ['-O2'],
        '3': ['-O3'],
        's': ['-Os'],
    }

    def __init__(self) -> None:
        super().__init__()
        # As of 19.0.0 ICC doesn't have sanitizer, color, or lto support.
        #
        # It does have IPO, which serves much the same purpose as LOT, but
        # there is an unfortunate rule for using IPO (you can't control the
        # name of the output file) which break assumptions meson makes
        self.base_options = ['b_pch', 'b_lundef', 'b_asneeded', 'b_pgo',
                             'b_coverage', 'b_ndebug', 'b_staticpic', 'b_pie']
        self.id = 'intel'
        self.lang_header = 'none'

    def get_pch_suffix(self) -> str:
        return 'pchi'

    def get_pch_use_args(self, pch_dir: str, header: str) -> T.List[str]:
        return ['-pch', '-pch_dir', os.path.join(pch_dir), '-x',
                self.lang_header, '-include', header, '-x', 'none']

    def get_pch_name(self, header_name: str) -> str:
        return os.path.basename(header_name) + '.' + self.get_pch_suffix()

    def openmp_flags(self) -> T.List[str]:
        if mesonlib.version_compare(self.version, '>=15.0.0'):
            return ['-qopenmp']
        else:
            return ['-openmp']

    def compiles(self, code: str, env: 'Environment', *,
                 extra_args: T.Union[None, T.List[str], 'CompilerArgs'] = None,
                 dependencies: T.Optional[T.List['Dependency']] = None,
                 mode: str = 'compile',
                 disable_cache: bool = False) -> T.Tuple[bool, bool]:
        extra_args = extra_args.copy() if extra_args is not None else []
        extra_args += [
            '-diag-error', '10006',  # ignoring unknown option
            '-diag-error', '10148',  # Option not supported
            '-diag-error', '10155',  # ignoring argument required
            '-diag-error', '10156',  # ignoring not argument allowed
            '-diag-error', '10157',  # Ignoring argument of the wrong type
            '-diag-error', '10158',  # Argument must be separate. Can be hit by trying an option like -foo-bar=foo when -foo=bar is a valid option but -foo-bar isn't
        ]
        return super().compiles(code, env, extra_args=extra_args, dependencies=dependencies, mode=mode, disable_cache=disable_cache)

    def get_profile_generate_args(self) -> T.List[str]:
        return ['-prof-gen=threadsafe']

    def get_profile_use_args(self) -> T.List[str]:
        return ['-prof-use']

    def get_buildtype_args(self, buildtype: str) -> T.List[str]:
        return self.BUILD_ARGS[buildtype]

    def get_optimization_args(self, optimization_level: str) -> T.List[str]:
        return self.OPTIM_ARGS[optimization_level]

    def get_has_func_attribute_extra_args(self, name: str) -> T.List[str]:
        return ['-diag-error', '1292']


class IntelVisualStudioLikeCompiler(VisualStudioLikeCompiler):

    """Abstractions for ICL, the Intel compiler on Windows."""

    BUILD_ARGS = {
        'plain': [],
        'debug': ["/Zi", "/traceback"],
        'debugoptimized': ["/Zi", "/traceback"],
        'release': [],
        'minsize': [],
        'custom': [],
    }  # type: T.Dict[str, T.List[str]]

    OPTIM_ARGS = {
        '0': ['/Od'],
        'g': ['/Od'],
        '1': ['/O1'],
        '2': ['/O2'],
        '3': ['/O3'],
        's': ['/Os'],
    }

    def __init__(self, target: str) -> None:
        super().__init__(target)
        self.id = 'intel-cl'

    def compiles(self, code: str, env: 'Environment', *,
                 extra_args: T.Union[None, T.List[str], 'CompilerArgs'] = None,
                 dependencies: T.Optional[T.List['Dependency']] = None,
                 mode: str = 'compile',
                 disable_cache: bool = False) -> T.Tuple[bool, bool]:
        # This covers a case that .get('foo', []) doesn't, that extra_args is
        if mode != 'link':
            extra_args = extra_args.copy() if extra_args is not None else []
            extra_args.extend([
                '/Qdiag-error:10006',  # ignoring unknown option
                '/Qdiag-error:10148',  # Option not supported
                '/Qdiag-error:10155',  # ignoring argument required
                '/Qdiag-error:10156',  # ignoring not argument allowed
                '/Qdiag-error:10157',  # Ignoring argument of the wrong type
                '/Qdiag-error:10158',  # Argument must be separate. Can be hit by trying an option like -foo-bar=foo when -foo=bar is a valid option but -foo-bar isn't
            ])
        return super().compiles(code, env, extra_args=extra_args, dependencies=dependencies, mode=mode, disable_cache=disable_cache)

    def get_toolset_version(self) -> T.Optional[str]:
        # Avoid circular dependencies....
        from ...environment import search_version

        # ICL provides a cl.exe that returns the version of MSVC it tries to
        # emulate, so we'll get the version from that and pass it to the same
        # function the real MSVC uses to calculate the toolset version.
        _, _, err = mesonlib.Popen_safe(['cl.exe'])
        v1, v2, *_ = search_version(err).split('.')
        version = int(v1 + v2)
        return self._calculate_toolset_version(version)

    def openmp_flags(self) -> T.List[str]:
        return ['/Qopenmp']

    def get_buildtype_args(self, buildtype: str) -> T.List[str]:
        return self.BUILD_ARGS[buildtype]

    def get_optimization_args(self, optimization_level: str) -> T.List[str]:
        return self.OPTIM_ARGS[optimization_level]

    def has_arguments(self, args: T.List[str], env: 'Environment', code: str, mode: str) -> T.Tuple[bool, bool]:
        warning_text = 'command line warning #10006'
        with self._build_wrapper(code, env, extra_args=args, mode=mode) as p:
            if p.returncode != 0:
                return False, p.cached
            return not(warning_text in p.stderr or warning_text in p.stdout), p.cached

