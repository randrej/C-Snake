# -*- coding: utf-8 -*-
import numpy as np
from abc import ABCMeta, abstractmethod
from typing import Iterable
from datetime import date

# public helper functions


def shape(array):
    """Return dimensions (shape) of a multidimensional list."""
    # strings should return nothing

    if isinstance(array, np.ndarray):
        return array.shape

    if isinstance(array, str):
        return ''
    curr = array
    shp = []

    while True:
        if not isinstance(curr, AnyArrayValue):
            return shp
        try:
            shp.append(len(curr))
            curr = curr[0]
        except (TypeError, IndexError):
            return shp


#types
class AnyInt(metaclass=ABCMeta):
    """Abstract class for any integer type: Python's int or numpy.integer."""


AnyInt.register(int)
AnyInt.register(np.integer)


class AnyFloat(metaclass=ABCMeta):
    """Abstract class for any floating type: Python's float or numpy.floating.
    """


AnyFloat.register(float)
AnyFloat.register(np.floating)


class AnyArrayValue(metaclass=ABCMeta):
    """Abstract class for any array type: any iterable that's not a dict or
    string."""

    @classmethod
    def __subclasshook__(cls, subclass):
        if cls is AnyArrayValue:
            if not issubclass(subclass,
                              (dict, str)) and issubclass(subclass, Iterable):
                return True
            return False
        return NotImplemented


class AnyStructValue(metaclass=ABCMeta):
    """Abstract class for any struct type: so far, AnyStructValue only."""


AnyStructValue.register(dict)

# classes defining C constructs


class EnumValue:
    """Singular value of an C-style enumeration."""

    def __init__(self, name, value=None, comment=None):
        self.name = name
        self.value = value
        self.comment = comment


class Enum:
    """C-style enumeration class."""

    def __init__(self, name, prefix="", typedef=False):

        self.typedef = typedef
        # enum values
        self.values = []
        self.name = name

        self.prefix = prefix

    def add_value(self, name, value=None, comment=None):
        """Assures that the user adds the values in the correct order."""
        self.values.append(EnumValue(name, value=value, comment=comment))


class FuncPtr:
    """Function pointer description."""

    def __init__(self, return_type, args=None, comment=None):
        self.return_type = return_type
        self.args = args

    def get_declaration(self, name):
        """Generate the whole declaration."""
        jointargs = self.args

        if isinstance(self.args, (AnyArrayValue)):
            jointargs = ', '.join(jointargs)

        retval = '{rt} (*{name})({args})'.format(
            rt=self.return_type,
            name=name,
            args=jointargs if self.args else '')

        return retval


class Variable:
    """C-style variable."""

    def __init__(self,
                 name,
                 primitive,
                 qualifiers=None,
                 array=None,
                 comment=None,
                 value=None,
                 value_opts=None):
        self.name = name
        self.primitive = primitive
        self.comment = comment
        self.array = array
        self.qualifiers = qualifiers
        self.value = value
        self.value_opts = value_opts

    def __array_dimensions(self):
        if isinstance(self.array, AnyArrayValue):
            array = "".join("[{0}]".format(dim) for dim in self.array)
        elif self.array is not None:
            array = "[{dim}]".format(dim=str(self.array))
        elif self.array is None and isinstance(self.value, str):
            array = '[]'
        elif self.array is None and shape(self.value):
            array = "".join("[{0}]".format(dim) for dim in shape(self.value))
        else:
            array = ""

        return array

    def declaration(self, extern=False):
        """Return a declaration string."""

        if not isinstance(self.qualifiers, str) and isinstance(
                self.qualifiers, Iterable):
            qual = " ".join(self.qualifiers) + " "
        elif self.qualifiers is not None:
            qual = str(self.qualifiers) + " "
        else:
            qual = ""

        array = self.__array_dimensions()

        if isinstance(self.primitive, FuncPtr):
            decl = self.primitive.get_declaration(self.name)

            return '{ext}{qual}{decl}{array}'.format(
                ext='extern ' if extern else '',
                qual=qual,
                decl=decl,
                array=array)

        return '{ext}{qual}{prim} {name}{array}'.format(
            ext='extern ' if extern else '',
            qual=qual,
            prim=self.primitive,
            name=self.name,
            array=array)

    def initialization(self, indent='    '):
        """Return an initialization string."""

        def generate_single_var(var_, formatstring=None):
            """Generate single variable."""

            if isinstance(var_, str):
                return "\"{val}\"".format(val=var_)
            elif isinstance(var_, Modifier):
                return var_.name
            elif isinstance(var_, bool):
                return 'true' if var_ else 'false'
            elif isinstance(var_, (AnyInt, AnyFloat)):
                if formatstring is None:
                    return str(var_)

                return formatstring.format(var_)

        def generate_array(array, indent='    ', formatstring=None):
            """Print (multi)dimensional arrays."""

            class OpenBrace:
                """Helper class to identify open braces while printing."""

            class ClosedBrace:
                """Helper class to identify closed braces while printing."""

            class Designator:
                """Helper class to identify struct designators."""

                def __init__(self, name):
                    self.name = name

            depth = 0
            stack = []
            stack.append(array)
            output = ''
            leading_comma = False

            while stack:
                top = stack.pop()
                # non-printed tokens

                if isinstance(top, AnyArrayValue):
                    stack.append(ClosedBrace())
                    stack.extend(top[::-1])
                    stack.append(OpenBrace())

                    continue

                if isinstance(top, AnyStructValue):
                    stack.append(ClosedBrace())
                    dict_pairs = [[value, Designator(key)]
                                  for key, value in top.items()][::-1]
                    flatdict = [
                        item for sublist in dict_pairs for item in sublist
                    ]
                    stack.extend(flatdict)
                    stack.append(OpenBrace())

                    continue
                # non-comma-delimited tokens

                if isinstance(top, ClosedBrace):
                    depth -= 1 if depth > 0 else 0
                    output += '}'

                    if stack:
                        if isinstance(stack[-1], ClosedBrace):
                            output += '\n' + (indent * (depth - 1))
                        elif isinstance(stack[-1], Designator):
                            output += ','
                        else:
                            output += ',\n' + (indent * depth)
                        leading_comma = False

                    continue
                # check the need for leading comma

                if leading_comma:
                    output += ', '
                else:
                    leading_comma = True
                # (potentially) comma delimited tokens

                if isinstance(top, OpenBrace):
                    output += '{'
                    depth += 1

                    if isinstance(stack[-1],
                                  (OpenBrace, AnyArrayValue, AnyStructValue)):
                        output += '\n' + (indent * depth)
                    leading_comma = False

                    continue

                if isinstance(top, (AnyInt, AnyFloat, str, bool, Modifier)):
                    output += generate_single_var(top, formatstring)

                    continue

                if isinstance(top, Designator):
                    output += '\n' + (indent * depth)
                    output += '.' + top.name + ' = '
                    leading_comma = False

                    continue

            return output

        # main part: generating initializer

        if not isinstance(self.qualifiers, str) and isinstance(
                self.qualifiers, Iterable):
            qual = " ".join(self.qualifiers) + " "
        elif self.qualifiers is not None:
            qual = str(self.qualifiers) + " "
        else:
            qual = ""

        array = self.__array_dimensions()

        if isinstance(self.value, (AnyArrayValue, AnyStructValue)):
            assignment = '\n' if len(shape(self.value)) > 1 else ''
            assignment += generate_array(self.value, indent, self.value_opts)
        else:
            assignment = generate_single_var(self.value, self.value_opts)

        assignment_string = ' = ' + assignment if assignment else ''

        if isinstance(self.primitive, FuncPtr):
            decl = self.primitive.get_declaration(self.name)

            return '{qual}{decl}{array}{assignment_string};'.format(
                qual=qual,
                decl=decl,
                array=array,
                assignment_string=assignment_string)

        return '{qual}{prim} {name}{array}{assignment_string};'.format(
            qual=qual,
            prim=self.primitive,
            name=self.name,
            array=array,
            assignment_string=assignment_string)


class Struct:
    """C-style struct class."""

    def __init__(self, name, typedef=False, comment=None):
        self.name = name  # definition name of this struct e.g. Struct_t
        self.variables = []
        self.comment = comment
        self.typedef = typedef

    def add_variable(self, variable):
        """Add another variable to struct."""

        if not isinstance(variable, Variable):
            raise TypeError("variable must be 'Variable'")
        self.variables.append(variable)


class Modifier(metaclass=ABCMeta):
    """Abstract base class for initialization modifiers.

    Sometimes we want to initialize a value to another variable, but in some
    more complicated manner: using the address-of operator, dereference
    operator, subscripting, typecasting... This is an ABC for those
    modifiers.
    """

    @property
    @abstractmethod
    def name(self):
        """Return a name for initialization."""
        pass


# no modifier is also a modifier!
Modifier.register(Variable)


class AddressOf(Modifier):
    """Address of (&) modifier for variable initialization."""

    def __init__(self, target):
        if not isinstance(target, (Modifier, Function)):
            raise TypeError("Modifiers can only be used with variables, "
                            "functions and modifiers.")
        self.target = target

    @property
    def name(self):
        return '&' + self.target.name


class Dereference(Modifier):
    """Dereference (*) modifier for variable initialization."""

    def __init__(self, target):
        if not isinstance(target, Modifier):
            raise TypeError(
                "Modifiers can only be used with variables and modifiers.")
        self.target = target

    @property
    def name(self):
        return '*' + self.target.name


class Typecast(Modifier):
    """Typecast modifier for variable initialization."""

    def __init__(self, target, cast):
        if not isinstance(target, Modifier):
            raise TypeError(
                "Modifiers can only be used with variables and modifiers.")
        self.target = target
        self.cast = cast

    @property
    def name(self):
        return '(' + self.cast + ')' + self.target.name


class Subscript(Modifier):
    """Subscript ([]) modifier for variable initialization."""

    def __init__(self, target, subscript):
        if not isinstance(target, Modifier):
            raise TypeError(
                "Modifiers can only be used with variables and modifiers.")

        if not isinstance(subscript, (AnyInt, Modifier, AnyArrayValue)):
            raise TypeError(
                "Subscript must be an AnyInt, Modifier (or Variable), list or"
                " tuple.")

        if not subscript:
            raise TypeError("Subscript must be non-empty.")

        if isinstance(subscript, (AnyInt, Modifier)):
            self.subscript = [subscript]
        else:
            self.subscript = subscript
        self.target = target

    @property
    def name(self):
        ret_str = ''

        for dim in self.subscript:
            if isinstance(dim, (AnyInt, str)):
                ret_str += '[' + str(dim) + ']'
            elif isinstance(dim, Modifier):
                ret_str += '[' + dim.name + ']'

        return self.target.name + ret_str


class Dot(Modifier):
    """Dot (.) modifier for variable initialization."""

    def __init__(self, target, item):
        if not isinstance(target, Modifier):
            raise TypeError(
                "Modifiers can only be used with variables and modifiers.")
        self.target = target
        self.item = item

    @property
    def name(self):
        if isinstance(self.item, str):
            return self.target.name + '.' + self.item
        elif isinstance(self.item, Modifier):
            return self.target.name + '.' + self.item.name


class Arrow(Modifier):
    """Arrow (->) modifier for variable initialization."""

    def __init__(self, target, item):
        if not isinstance(target, Modifier):
            raise TypeError(
                "Modifiers can only be used with variables and modifiers.")
        self.target = target
        self.item = item

    @property
    def name(self):
        if isinstance(self.item, str):
            return self.target.name + '->' + self.item
        elif isinstance(self.item, Modifier):
            return self.target.name + '->' + self.item.name


class GenericModifier(Modifier):
    """Generic modifier

    Expects a formatstring that uses {0} to signify variable name.
    """

    def __init__(self, target, formatstring):
        if target and not isinstance(target, Modifier):
            raise TypeError(
                "Modifiers can only be used with variables and modifiers.")
        self.target = target
        self.formatstring = formatstring

    @property
    def name(self):
        if self.target:
            return self.formatstring.format(self.target.name)

        return self.formatstring


class OffsetOf(Modifier):
    """Offsetof (->) modifier for initializing variables to offsets of struct
    members.
    """

    def __init__(self, struct, member):
        if not isinstance(struct, (str, Struct)):
            raise TypeError(
                'Modifiers can only be used with struct names and structs')
        self.struct = struct
        self.member = member

    @property
    def name(self):
        if isinstance(self.struct, str):
            struct_name = self.struct
        elif isinstance(self.struct, Struct):
            if self.struct.typedef:
                struct_name = self.struct.name
            else:
                struct_name = 'struct ' + self.struct.name

        if isinstance(self.member, str):
            member_name = self.member
        elif isinstance(self.member, Modifier):
            member_name = self.member.name

        return 'offsetof({struct}, {memb})'.format(
            struct=struct_name, memb=member_name)


class TextModifier(Modifier):
    """Generic modifier that just contains arbitrary text to be used to
    initialize a value."""

    def __init__(self, text):
        self.text = text

    @property
    def name(self):
        return str(self.text)


class Function:
    """C-style function."""

    def __init__(self, name, return_type='void', qualifiers=[]):
        self.name = name
        self.return_type = return_type
        self.variables = []
        self.code = ''
        if isinstance(qualifiers, str):
            self.qualifiers = [qualifiers]
        else:
            self.qualifiers = qualifiers

    def add_argument(self, var):
        """Add an argument to function."""

        if not isinstance(var, Variable):
            raise TypeError("variable must be of type 'Variable'")

        self.variables.append(var)

    def prototype(self):
        """Generate function prototype string."""

        prot = '{qual}{ret} {nm}({args})'.format(
            qual=' '.join(self.qualifiers) + ' ' if self.qualifiers else '',
            ret=self.return_type,
            nm=self.name,
            args=', '.join([v.declaration() for v in self.variables]) if
            self.variables else 'void')

        return prot

    def add_code(self, code):
        """Add some code to the body of the function."""

        if isinstance(code, list):
            code = '\n'.join(code)

        if isinstance(code, CodeWriter):
            code = code.code

        if not isinstance(code, (str, list, CodeWriter)):
            raise TypeError("text must be a 'str', 'list' or a 'CodeWriter'.")

        self.code += code + '\n'

    def call(self, *arg):
        """Call a function."""

        if not len(arg) == len(self.variables):
            raise ValueError(
                "number of arguments must match number of variables")

        call_ = '{name}({args});'.format(
            name=self.name, args=', '.join([str(a) for a in arg]))

        return call_


# Main, file-generating class


class CodeWriter:
    """Class to describe and generate contents of a .c/.cpp/.h/.hpp file."""

    CPP = "__cplusplus"

    VERSION = "1.1"

    def __init__(self, lf="\n", indent=4):

        self.line_feed = lf

        if isinstance(indent, AnyInt):
            self.indent = ' ' * indent
        else:
            self.indent = indent

        # initialize values
        self.commenting = False  # switch for bulk commenting
        self.defs = []  # define levels
        self.switch = []  # switch levels
        self.tabs = 0
        self.text = ''  # code

    def tab_in(self):
        """Increase tab level."""
        self.tabs += 1

    def tab_out(self):
        """Decrease tab level."""

        if self.tabs > 0:
            self.tabs -= 1

    def reset_tabs(self):
        self.tabs = 0

    def start_comment(self):
        """Start a bulk comment."""
        self.add_line('/*')
        self.commenting = True

    def end_comment(self):
        """End a bulk comment."""
        self.commenting = False
        self.add_line('*/')

    def add_autogen_comment(self, source=None):
        """Add the auto-gen comment (user can point to the source file if required)."""
        self.start_comment()
        self.add_line(
            "This file was autogenerated using the C-Snake v{version} script".
            format(version=self.VERSION))
        self.add_line(
            "This file should not be edited directly, any changes will be overwritten next time the script is run"
        )

        if source:
            self.add_line(
                "Make any changes to the file '{src}'".format(src=str(source)))
        self.add_line(
            "Source code for C-Snake available at https://github.com/SchrodingersGat/C-Snake"
        )
        self.end_comment()

    def add_license_comment(self, license_, authors, intro=None):
        """Add the license comment."""
        self.start_comment()

        if intro:
            for line in intro.splitlines():
                if line == '':
                    self.add_line()
                else:
                    self.add_line(line)

        year = date.today().year

        if authors:
            for author in authors:
                self.add_line("Copyright © {year} {name}{email}".format(
                    year=year,
                    name=author['name'],
                    email=' <{0}>'.format(author['email']) if
                    author.get('email', None) else ''))
        self.add_line()

        if not isinstance(license_, str):
            raise TypeError('license_ must be a string.')

        for line in license_.splitlines():
            self.add_line(line)

        self.end_comment()

    def open_brace(self):
        """Open-brace and tab."""
        self.add_line('{')
        self.tab_in()

    def close_brace(self, new_line=True):
        """Close-brace and tab-out."""
        self.tab_out()
        self.add(self.indent * self.tabs + '}')

        if new_line:
            self.add_line('')

    def define(self, name, value=None, comment=None):
        """Add a define."""
        line = "#define " + name

        if value:
            line += ' ' + str(value)

        self.add_line(line, comment=comment, ignore_tabs=True)

    def start_if_def(self, define, invert=False, comment=None):
        """Start an #ifdef block (preprocessor)."""
        self.defs.append(define)

        if invert:
            self.add_line(
                "#ifndef " + define, comment=comment, ignore_tabs=True)
        else:
            self.add_line(
                "#ifdef " + define, comment=comment, ignore_tabs=True)

    def end_if_def(self):
        """End an #ifdef block."""

        if self.defs:
            self.add_line("#endif ", comment=self.defs.pop(), ignore_tabs=True)
        else:
            self.add_line("#endif", ignore_tabs=True)

    def cpp_entry(self):
        """Add an 'extern' switch for CPP compilers."""
        self.start_if_def(self.CPP, "Play nice with C++ compilers")
        self.add_line('extern "C" {', ignore_tabs=True)
        self.end_if_def()

    def cpp_exit(self):
        self.start_if_def(self.CPP, "Done playing nice with C++ compilers")
        self.add_line('}', ignore_tabs=True)
        self.end_if_def()

    def start_switch(self, switch):
        """Start a switch statement."""
        self.switch.append(switch)
        self.add_line('switch ({sw})'.format(sw=switch))
        self.open_brace()

    def end_switch(self):
        """End a switch statement."""
        self.tab_out()
        self.add('}')

        if self.switch:
            self.add(' // ~switch ({sw})'.format(sw=self.switch.pop()))
        self.add_line()

    def add_case(self, case, comment=None):
        """Add a case statement."""
        self.add_line('case {case}:'.format(case=case), comment=comment)
        self.tab_in()

    def add_default(self, comment=None):
        """Add a default case statement."""
        self.add_line('default:', comment=comment)
        self.tab_in()

    def break_from_case(self):
        """Break from a case."""
        self.add_line('break;')
        self.tab_out()

    def return_from_case(self, value=None):
        """Return from a case."""
        self.add_line(
            'return{val};'.format(val=' ' + str(value) if value else ''))
        self.tab_out()

    def add(self, text):
        """Add raw text."""
        self.text += text

    def add_line(self, text=None, comment=None, ignore_tabs=False):
        """Add a line of (formatted) text."""

        # empty line

        if not text and not comment and not self.commenting:
            self.add(self.line_feed)

            return

        if not ignore_tabs and not self.commenting:
            self.add(self.indent * self.tabs)

        if self.commenting:
            self.add("* ")

        # add the text (if appropriate)

        if text:
            self.add(text)
        # add a trailing comment (if appropriate)

        if comment:
            if text:
                self.add(' ')  # add a space after the text
            self.add('//' + comment)

        self.add(self.line_feed)

    def include(self, file, comment=None):
        """Add a c-style include."""
        self.add_line(
            "#include {file}".format(file=file),
            comment=comment,
            ignore_tabs=True)

    def add_enum(self, enum):
        """Add a constructed enumeration."""

        if not isinstance(enum, Enum):
            raise TypeError('enum must be of type "Enum"')

        if enum.typedef:
            self.add_line("typedef enum")
        else:
            self.add_line("enum {name}".format(name=enum.name))
        self.open_brace()

        for i, v in enumerate(enum.values):
            line = enum.prefix + v.name

            if v.value:
                line += " = " + str(v.value)

            if i < (len(enum.values) - 1):
                line += ","

            self.add_line(line, comment=v.comment)

        self.close_brace(new_line=False)

        if enum.typedef:
            self.add(' ' + enum.name + ';')
        else:
            self.add(';')
        self.add_line()

    def add_variable_declaration(self, var, extern=False):
        """Add a variable declaration."""

        if not isinstance(var, Variable):
            raise TypeError("variable must be of type 'Variable'")

        self.add_line(var.declaration(extern) + ";", comment=var.comment)

    def add_variable_initialization(self, var):
        """Add a variable initialization."""

        if not isinstance(var, Variable):
            raise TypeError("variable must be of type 'Variable'")

        initlines = var.initialization(self.indent).splitlines()
        self.add_line(initlines[0], comment=var.comment)

        if len(initlines) > 1:
            self.tab_in()

            for line in initlines[1:]:
                self.add_line(line)
            self.tab_out()

    def add_struct(self, struct):
        """Add a struct."""

        if not isinstance(struct, Struct):
            raise TypeError("struct must be of type 'Struct'")

        if struct.typedef:
            self.add_line("typedef struct")
        else:
            self.add_line("struct {name}".format(name=struct.name))
        self.open_brace()

        for var in struct.variables:
            if isinstance(var, Variable):  # variables within the struct
                self.add_variable_declaration(var)

        self.close_brace(new_line=False)

        if struct.typedef:
            self.add(' ' + struct.name + ';')
        else:
            self.add(';')
        self.add_line()

    def add_function_prototype(self, func, extern=False, comment=None):
        """Add a function prototype."""

        if not isinstance(func, Function):
            raise TypeError("func must be of type 'Function'")

        self.add_line(
            ('extern' if extern else '') + func.prototype() + ';',
            comment=comment)

    def add_function_definition(self, func, comment=None):
        """Add a function definition."""

        if not isinstance(func, Function):
            raise TypeError("Argument func must be of type 'Function'")

        self.add_line(func.prototype(), comment=comment)
        self.open_brace()

        for line in func.code.splitlines():
            if line == '':
                self.add_line()
            else:
                self.add_line(line)
        self.close_brace()

    def call_function(self, func, *arg):
        """Enter a function."""

        if not isinstance(func, Function):
            raise TypeError("func must be of type 'Function'")

        self.add_line(func.call(*arg))

    def write_to_file(self, file):
        """Write code to file."""
        with open(file, 'w') as the_file:
            the_file.write(self.text)
