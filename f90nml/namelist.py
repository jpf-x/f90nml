"""f90nml.namelist
   ===============

   Tools for creating Fortran namelist files from Python ``dict``s.

   :copyright: Copyright 2014 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""
from __future__ import print_function

from datetime import datetime
import os
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict


class NmlDict(OrderedDict):
    """Case-insensitive Python dict"""

    def __init__(self, *args, **kwds):
        super(NmlDict, self).__init__(*args, **kwds)

        for key, val in self.items():
            if isinstance(val, dict):
                self[key] = NmlDict(val)

        # Formatting properties
        self._colwidth = 72
        self._indent = 4 * ' '
        self._end_comma = False
        self._uppercase = False

    def __contains__(self, key):
        return super(NmlDict, self).__contains__(key.lower())

    def __delitem__(self, key):
        return super(NmlDict, self).__delitem__(key.lower())

    def __getitem__(self, key):
        return super(NmlDict, self).__getitem__(key.lower())

    def __setitem__(self, key, value):
        super(NmlDict, self).__setitem__(key.lower(), value)

    # Format configuration

    @property
    def colwidth(self):
        """Return the target column width of the namelist file."""
        return self._colwidth

    @colwidth.setter
    def colwidth(self, width):
        """Validate and set the column width."""
        if isinstance(width, int):
            if width >= 0:
                self._colwidth = width
            else:
                raise ValueError('Column width must be nonnegative.')
        else:
            raise TypeError('Column width must be a nonnegative integer.')

    @property
    def indent(self):
        """Return the indentation string within namelist group entries."""
        return self._indent

    @indent.setter
    def indent(self, value):
        """Validate and set the indent width, either as an explicit whitespace
        string or by the number of whitespace characters.
        """

        # Explicit indent setting
        if isinstance(value, str):
            if value.isspace():
                self._indent = value
            else:
                raise ValueError('String indentation can only contain '
                                 'whitespace.')

        # Set indent width
        elif isinstance(value, int):
            if value >= 0:
                self._indent = value * ' '
            else:
                raise ValueError('Indentation spacing must be nonnegative.')

        else:
            raise TypeError('Indentation must be specified by string or space '
                            'width.')

    @property
    def end_comma(self):
        """Return True if entries are terminated with commas."""
        return self._end_comma

    @end_comma.setter
    def end_comma(self, value):
        """Validate and set the comma termination flag."""
        if not isinstance(value, bool):
            raise TypeError('end_comma attribute must be a logical type.')
        self._end_comma = value

    @property
    def uppercase(self):
        """Return True if names are displayed in upper case."""
        return self._uppercase

    @uppercase.setter
    def uppercase(self, value):
        """Validate and set the upper case flag."""
        if not isinstance(value, bool):
            raise TypeError('uppercase attribute must be a logical type.')
        self._uppercase = value

    # File output

    def write(self, nml_path, force=False):
        """Output dict to a Fortran 90 namelist file."""

        if not force and os.path.isfile(nml_path):
            raise IOError('File {0} already exists.'.format(nml_path))

        with open(nml_path, 'w') as nml_file:
            for grp_name, grp_vars in self.items():
                # Check for repeated namelist records (saved as lists)
                if type(grp_vars) is list:
                    for g_vars in grp_vars:
                        self.write_nmlgrp(grp_name, g_vars, nml_file)
                else:
                    self.write_nmlgrp(grp_name, grp_vars, nml_file)

        if self.items():
            with open(nml_path, 'rb+') as nml_file:
                nml_file.seek(-1, os.SEEK_END)
                nml_file.truncate()

    def write_nmlgrp(self, grp_name, grp_vars, nml_file):
        """Write namelist group to target file."""

        if self.uppercase:
            grp_name = grp_name.upper()

        print('&{0}'.format(grp_name), file=nml_file)

        for v_name, v_val in grp_vars.items():

            for v_str in self.var_strings(v_name, v_val):
                nml_line = self.indent + '{0}'.format(v_str)
                print(nml_line, file=nml_file)

        print('/', file=nml_file)
        print(file=nml_file)

    def var_strings(self, v_name, v_values):
        """Convert namelist variable to list of fixed-width strings."""

        if self.uppercase:
            v_name = v_name.upper()

        var_strs = []

        # Parse derived type contents
        if isinstance(v_values, dict):
            for f_name, f_vals in v_values.items():
                v_title = '%'.join([v_name, f_name])

                v_strs = self.var_strings(v_title, f_vals)
                var_strs.extend(v_strs)

        # Parse an array of derived types
        elif (isinstance(v_values, list) and
              any(isinstance(v, dict) for v in v_values) and
              all((isinstance(v, dict) or v is None) for v in v_values)):
            for idx, val in enumerate(v_values, start=1):

                if val is None:
                    continue

                v_title = v_name + '({0})'.format(idx)

                v_strs = self.var_strings(v_title, val)
                var_strs.extend(v_strs)

        else:
            if not type(v_values) is list:
                v_values = [v_values]

            # Split output across multiple lines (if necessary)
            val_strs = []

            val_line = ''
            for v_val in v_values:

                v_width = self.colwidth - len(self.indent + v_name + ' = ')

                if len(val_line) < v_width:
                    val_line += self.f90repr(v_val) + ', '

                if len(val_line) >= v_width:
                    val_strs.append(val_line.rstrip())
                    val_line = ''

            # Append any remaining values
            if val_line:
                if (self.end_comma or
                        (len(v_values) > 1 and v_values[-1] is None)):
                    val_strs.append(val_line)
                else:
                    val_strs.append(val_line[:-2])

            # Complete the set of values
            var_strs.append('{0} = {1}'.format(v_name, val_strs[0]).strip())

            for v_str in val_strs[1:]:
                var_strs.append(' ' * (len(v_name + ' = ')) + v_str)

        return var_strs

    def f90repr(self, value):
        """Convert primitive Python types to equivalent Fortran strings."""

        if type(value) is int:
            return str(value)
        elif type(value) is float:
            return str(value)
        elif type(value) is bool:
            return '.{0}.'.format(str(value).lower())
        elif type(value) is complex:
            return '({0}, {1})'.format(value.real, value.imag)
        elif type(value) is str:
            return repr(value).replace("\\'", "''").replace('\\"', '""')
        elif value is None:
            return ''
        else:
            raise ValueError('Type {0} of {1} cannot be converted to a '
                             'Fortran type.'.format(type(value), value))
