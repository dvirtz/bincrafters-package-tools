import json
import os
import subprocess
import typing

from bincrafters.build_shared import PLATFORMS

def prepare_env(platform: str, config: json, select_config: str = None, set_env_variable: typing.Callable[[str, str], None] = None):
    if platform not in PLATFORMS:
        raise ValueError("Only GitHub Actions, Azure Pipelines and GitLab are supported at this point.")

    if platform != "azp" and select_config is not None:
        raise ValueError("The --select-config parameter can only be used with Azure Pipelines.")

    if select_config:
        config = config[select_config]

    def _set_env_variable(var_name: str, value: str):
        print("{} = {}".format(var_name, value))
        os.environ[var_name] = value
        if platform == "gha":
            if compiler in ["VISUAL", "MSVC"]:
                os.system('echo {}={}>> {}'.format(var_name, value, os.getenv("GITHUB_ENV")))
            else:
                subprocess.run(
                    'echo "{}={}" >> $GITHUB_ENV'.format(var_name, value),
                    shell=True
                )

        elif platform == "azp":
            if compiler in ["VISUAL", "MSVC"]:
                subprocess.run(
                    'echo ##vso[task.setvariable variable={}]{}'.format(var_name, value),
                    shell=True
                )
            else:
                subprocess.run(
                    'echo "##vso[task.setvariable variable={}]{}"'.format(var_name, value),
                    shell=True
                )

    set_env_variable = set_env_variable or _set_env_variable

    def _options_str(options: typing.Dict[str, typing.Dict[str, str]]):
        options_str = []
        for package, package_options in options.items():
            for option_name, option_val in package_options.items():
                options_str.append("{}:{}={}".format(package, option_name, option_val))
        return ",".join(options_str)

    compiler = config["compiler"]
    compiler_version = config["version"]
    docker_image = config.get("dockerImage", "")
    build_type = config.get("buildType", "")
    options = config.get("options")

    set_env_variable("BPT_CWD", config["cwd"])
    set_env_variable("CONAN_VERSION", config["recipe_version"])

    if compiler == "APPLE_CLANG":
        if "." not in compiler_version:
            compiler_version = "{}.0".format(compiler_version)

    set_env_variable("CONAN_{}_VERSIONS".format(compiler), compiler_version)

    if compiler == "GCC" or compiler == "CLANG":
        if docker_image == "":
            compiler_lower = compiler.lower()
            version_without_dot = compiler_version.replace(".", "")
            if (compiler == "GCC" and float(compiler_version) >= 11) or \
                    (compiler == "CLANG" and float(compiler_version) >= 12):
                # Use "modern" CDT containers for newer compilers
                docker_image = "conanio/{}{}-ubuntu16.04".format(compiler_lower, version_without_dot)
            else:
                docker_image = "conanio/{}{}".format(compiler_lower, version_without_dot)
        set_env_variable("CONAN_DOCKER_IMAGE", docker_image)

    if build_type != "":
        set_env_variable("CONAN_BUILD_TYPES", build_type)

    if options:
        set_env_variable("CONAN_OPTIONS", _options_str(options))

    if platform == "gha" or platform == "azp":
        if compiler == "APPLE_CLANG":
            xcode_mapping = {
                "9.1": "/Applications/Xcode_9.4.1.app",
                "10.0": "/Applications/Xcode_10.3.app",
                "11.0": "/Applications/Xcode_11.5.app",
                "12.0": "/Applications/Xcode_12.4.app",
            }
            if compiler_version in xcode_mapping:
                subprocess.run(
                    'sudo xcode-select -switch "{}"'.format(xcode_mapping[compiler_version]),
                    shell=True
                )
                print('executing: xcode-select -switch "{}"'.format(xcode_mapping[compiler_version]))

            subprocess.run(
                'clang++ --version',
                shell=True
            )

        if compiler in ["VISUAL", "MSVC"]:
            with open(os.path.join(os.path.dirname(__file__), "prepare_env_azp_windows.ps1"), "r") as file:
                content = file.read()
                file.close()

            with open("execute.ps1", "w", encoding="utf-8") as file:
                file.write(content)
                file.close()

            subprocess.run("pip install --upgrade cmake", shell=True, check=True)
            subprocess.run("powershell -file {}".format(os.path.join(os.getcwd(), "execute.ps1")), shell=True, check=True)

    if platform == "gha" and (compiler == "GCC" or compiler == "CLANG"):
        subprocess.run('docker system prune --all --force --volumes', shell=True)
        subprocess.run('sudo rm -rf "/usr/local/share/boost"', shell=True)
        subprocess.run('sudo rm -rf "$AGENT_TOOLSDIRECTORY/CodeQL"', shell=True)
        subprocess.run('sudo rm -rf "$AGENT_TOOLSDIRECTORY/Ruby"', shell=True)
        subprocess.run('sudo rm -rf "$AGENT_TOOLSDIRECTORY/boost"', shell=True)
        subprocess.run('sudo rm -rf "$AGENT_TOOLSDIRECTORY/go"', shell=True)
        subprocess.run('sudo rm -rf "$AGENT_TOOLSDIRECTORY/node"', shell=True)

    if platform != "gl":
        subprocess.run("conan user", shell=True)
