from typing import Callable

from enum import Enum

import json
import os
import re
import shutil

from utility import camel_to_snake, check_command


class ProjectType(Enum):
    LIBRARY = 1
    EXECUTABLE = 2
    SWIFTUI_APP = 3


def _find_getch() -> Callable[[], str]:
    try:
        import termios
    except ImportError:
        # Probably Windows.
        import msvcrt

        return msvcrt.getch

    # Unix.
    import sys
    import tty

    def _getch() -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    return _getch


getch = _find_getch()


util_dir = os.path.dirname(os.path.realpath(__file__))
repo_dir = os.path.dirname(util_dir)

sources_dir = os.path.join(repo_dir, 'Sources')


def setup(project_name: str, project_type: ProjectType, git_repo: bool) -> int:
    print('Setting up {}...'.format(project_name))

    os.chdir(repo_dir)
    if not check_command('swift', 'Swift', 'https://swift.org/getting-started/#installing-swift'):
        return 1
    if not check_command('cargo', 'Cargo', 'https://doc.rust-lang.org/cargo/getting-started/installation.html'):
        return 1
    if not check_command('uniffi-bindgen', 'uniffi-bindgen', 'https://mozilla.github.io/uniffi-rs/'):
        return 1

    json_string = os.popen('swift package dump-package').read()
    json_dict = json.loads(json_string)
    old_project_name = json_dict['name']
    if old_project_name != 'UniFFITemplate':
        print('This project has already been set up.')
        return 1

    uniffi_version = os.popen('uniffi-bindgen --version').read().split(' ')[1].strip()

    project_name_snake = camel_to_snake(project_name)

    main_module_dir = os.path.join(sources_dir, project_name)
    bindings_module_dir = os.path.join(sources_dir, project_name + 'Bindings')
    c_bindings_module_dir = os.path.join(sources_dir, project_name + 'CBindings')
    c_bindings_path = os.path.join(c_bindings_module_dir, project_name + 'CBindings.c')
    c_bindings_header_path = os.path.join(c_bindings_module_dir, 'include', project_name + 'CBindings.h')
    rust_module_dir = os.path.join(sources_dir, project_name + 'Rust')
    cargo_dir = os.path.join(rust_module_dir, 'cargo')
    cargo_src_dir = os.path.join(cargo_dir, 'src')
    udl_path = os.path.join(cargo_src_dir, project_name_snake + '.udl')

    os.rename(os.path.join(sources_dir, 'UniFFITemplate'), main_module_dir)
    os.rename(os.path.join(sources_dir, 'UniFFITemplateBindings'), bindings_module_dir)
    os.rename(os.path.join(sources_dir, 'UniFFITemplateCBindings'), c_bindings_module_dir)
    os.rename(os.path.join(c_bindings_module_dir, 'UniFFITemplateCBindings.c'), c_bindings_path)
    os.rename(os.path.join(c_bindings_module_dir, 'include', 'UniFFITemplateCBindings.h'), c_bindings_header_path)
    os.rename(os.path.join(sources_dir, 'UniFFITemplateRust'), rust_module_dir)
    os.rename(os.path.join(cargo_src_dir, 'uniffi_template.udl'), udl_path)

    for path in [c_bindings_path, c_bindings_header_path]:
        with open(path, 'r') as f:
            content = f.read()
        content = content.replace('UniFFITemplate', project_name)
        with open(path, 'w') as f:
            f.write(content)

    for root, _, files in os.walk(cargo_dir):
        for file in files:
            path = os.path.join(root, file)
            with open(path, 'r') as f:
                content = f.read()
            content = content.replace('UniFFITemplate', project_name)
            content = content.replace('uniffi_template', project_name_snake)
            if file == 'Cargo.toml':
                content = content.replace('uniffi = "0.21.0"', 'uniffi = "{}"'.format(uniffi_version))
                content = content.replace('uniffi_macros = "0.21.0"', 'uniffi_macros = "{}"'.format(uniffi_version))
                content = content.replace('uniffi_build = "0.21.0"', 'uniffi_build = "{}"'.format(uniffi_version))
            with open(path, 'w') as f:
                f.write(content)

    regexes_to_replace = []
    if project_type == ProjectType.LIBRARY:
        library_file_path = os.path.join(main_module_dir, project_name + '.swift')

        os.rename(os.path.join(main_module_dir, 'UniFFITemplate.swift'), library_file_path)

        with open(library_file_path, 'r') as f:
            content = f.read()
        content = content.replace('UniFFITemplate', project_name)
        with open(library_file_path, 'w') as f:
            f.write(content)
    elif project_type == ProjectType.EXECUTABLE:
        os.remove(os.path.join(main_module_dir, 'UniFFITemplate.swift'))

        with open(os.path.join(main_module_dir, 'main.swift'), 'x') as f:
            f.write('import {}\n\n'.format(project_name + 'Bindings'))
            f.write('print({}.add(a: 5, b: 6))\n'.format(project_name + 'Bindings'))

        regexes_to_replace.append((re.compile(r'\.library\(([\s\n]*)name: "UniFFITemplate"'), r'.executable(\1name: "{}"'.format(project_name)))
        regexes_to_replace.append((re.compile(r'\.target\(([\s\n]*)name: "UniFFITemplate"'), r'.executableTarget(\1name: "{}"'.format(project_name)))
    elif project_type == ProjectType.SWIFTUI_APP:
        os.remove(os.path.join(main_module_dir, 'UniFFITemplate.swift'))

        with open(os.path.join(main_module_dir, '{}App.swift'.format(project_name)), 'x') as f:
            f.write('import SwiftUI\n\n')
            f.write('@main\n')
            f.write('struct {}App: App {{\n'.format(project_name))
            f.write('    var body: some Scene {\n')
            f.write('        WindowGroup {\n')
            f.write('            ContentView()\n')
            f.write('        }\n')
            f.write('    }\n')
            f.write('}\n')

        with open(os.path.join(main_module_dir, 'ContentView.swift'), 'x') as f:
            f.write('import SwiftUI\nimport {}\n\n'.format(project_name + 'Bindings'))
            f.write('struct ContentView: View {\n')
            f.write('    @State var a: UInt32 = 5\n')
            f.write('    @State var b: UInt32 = 6\n\n')
            f.write('    var body: some View {\n')
            f.write('        VStack {\n')
            f.write('            Text("Add two numbers using Rust:")\n')
            f.write('            TextField("A", value: self.$a, formatter: NumberFormatter())\n')
            f.write('                .textFieldStyle(.roundedBorder)\n')
            f.write('            TextField("B", value: self.$b, formatter: NumberFormatter())\n')
            f.write('                .textFieldStyle(.roundedBorder)\n')
            f.write('            Divider()\n')
            f.write('            Text("\\(self.a) + \\(self.b) = \\({}.add(a: self.a, b: self.b))")\n'.format(project_name + 'Bindings'))
            f.write('        }.padding()\n')
            f.write('    }\n')
            f.write('}\n')

        regexes_to_replace.append((re.compile(r'\.library\(([\s\n]*)name: "UniFFITemplate"'), r'.executable(\1name: "{}"'.format(project_name)))
        regexes_to_replace.append((re.compile(r'\.target\(([\s\n]*)name: "UniFFITemplate"'), r'.executableTarget(\1name: "{}"'.format(project_name)))


    regexes_to_replace.append((re.compile(r'UniFFITemplate'), project_name))

    with open(os.path.join(repo_dir, 'Package.swift'), 'r') as f:
        content = f.read()
    for regex, replacement in regexes_to_replace:
        content = regex.sub(replacement, content)
    with open(os.path.join(repo_dir, 'Package.swift'), 'w') as f:
        f.write(content)

    os.system('swift package tools-version --set-current')


    if git_repo:
        shutil.rmtree(os.path.join(repo_dir, '.git'))
        os.system('git init')

        with open(os.path.join(repo_dir, 'README.md'), 'w') as f:
            f.write('# {}\n\n'.format(project_name))
            f.write('This project was created using [UniFFITemplate](https://github.com/Zollerboy1/UniFFITemplate).\n\n')
            f.write('To build the project, first run `./util/build [--release]` and then `swift build [-c release]`.\n')

    print('Done!')

    return 0


def main(args: list[str]) -> int:
    if len(args) > 0:
        print('Setup script doesn\'t accept any arguments for now.')
        return 2

    print('Project name: ', end='')
    project_name = input()

    print('Available project types:')
    print('1. Library')
    print('2. Executable')
    print('3. SwiftUI App')
    print('Project type: ', end='')
    project_type = ProjectType(int(input()))

    print('Should a new git repository be setup? [Y/n] ', end='', flush=True)

    answer = getch()
    while answer.lower() not in ('y', 'n', '\r', '\n'):
        answer = getch()

    git_repo = answer.lower() != 'n'

    print()

    return setup(project_name, project_type, git_repo)

