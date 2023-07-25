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

    json_string = os.popen('swift package dump-package').read()
    json_dict = json.loads(json_string)
    old_project_name = json_dict['name']
    if old_project_name != 'UniFFITemplate':
        print('This project has already been set up.')
        return 1

    project_name_snake = camel_to_snake(project_name)

    gitignore_path = os.path.join(repo_dir, '.gitignore')
    main_module_dir = os.path.join(sources_dir, project_name)
    bindings_module_dir = os.path.join(sources_dir, project_name + 'Bindings')
    c_bindings_module_dir = os.path.join(sources_dir, project_name + 'CBindings')
    c_bindings_path = os.path.join(c_bindings_module_dir, project_name + 'CBindings.c')
    c_bindings_header_path = os.path.join(c_bindings_module_dir, 'include', project_name + 'CBindings.h')
    cargo_toml_path = os.path.join(repo_dir, 'Cargo.toml')
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

    with open(gitignore_path, 'r') as f:
        content = f.read()
    content.replace('\nCarg.lock', '')
    with open(gitignore_path, 'w') as f:
        f.write(content)

    for path in [c_bindings_path, c_bindings_header_path, cargo_toml_path]:
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
            f.write('    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate\n\n')
            f.write('    var body: some Scene {\n')
            f.write('        WindowGroup {\n')
            f.write('            ContentView()\n')
            f.write('        }\n')
            f.write('    }\n')
            f.write('}\n\n')
            f.write('class AppDelegate: NSObject, NSApplicationDelegate {\n')
            f.write('    func applicationDidFinishLaunching(_ aNotification: Notification) {\n')
            f.write('        NSApp.setActivationPolicy(.regular)\n')
            f.write('        NSApp.activate(ignoringOtherApps: true)\n')
            f.write('        NSApp.windows.first?.makeKeyAndOrderFront(nil)\n')
            f.write('    }\n\n')
            f.write('    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {\n')
            f.write('        true\n')
            f.write('    }\n')
            f.write('}\n')

        with open(os.path.join(main_module_dir, 'ContentView.swift'), 'x') as f:
            f.write('import SwiftUI\nimport {}\n\n'.format(project_name + 'Bindings'))
            f.write('struct ContentView: View {\n')
            f.write('    @State var a: Int32 = 5\n')
            f.write('    @State var b: Int32 = 6\n\n')
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

        regexes_to_replace.append((re.compile(r'products:'), r'platforms: [.macOS(.v11)],\n    products:'))
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
            f.write('To build your code, run the following commands:\n\n')
            f.write('```bash\n')
            f.write('./util/build\n')
            f.write('swift build\n')
            f.write('```\n\n')
            f.write('or\n\n')
            f.write('```bash\n')
            f.write('./util/build --release\n')
            f.write('swift build -c release\n')
            f.write('```\n\n')
            f.write('The build script will build the cargo package located at `Sources/{}Rust/cargo`, generate the Swift bindings for it, and put them into the right place so that `swift build` can find them.\n\n'.format(project_name))
            f.write('Every time you have changed something in the cargo package (while keeping the `.udl` file up to date), you have to use `./util/build` again, so that the changes become visible in the Swift bindings.\n')

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
    project_type_input = input()
    while not project_type_input.isdigit() or int(project_type_input) not in (1, 2, 3):
        print('Invalid project type. Please enter a number between 1 and 3: ', end='')
        project_type_input = input()
    project_type = ProjectType(int(project_type_input))

    print('Should a new git repository be setup? [Y/n] ', end='', flush=True)

    answer = getch()
    while answer.lower() not in ('y', 'n', '\r', '\n'):
        answer = getch()

    git_repo = answer.lower() != 'n'

    print()

    return setup(project_name, project_type, git_repo)

