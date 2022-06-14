package main

import (
	"dagger.io/dagger"
	"universe.dagger.io/docker"
)

dagger.#Plan & {

	client: {
		filesystem: {
			"./": read: contents:             dagger.#FS
			"./evap_or_ac": write: contents:  actions.clean.black.export.directories."/workdir/evap_or_ac"
			"./tests": write: contents:       actions.clean.black.export.directories."/workdir/tests"
			"./project.cue": write: contents: actions.clean.cue.export.files."/workdir/project.cue"
		}
	}
	python_version: string | *"3.9"
	poetry_version: string | *"1.1.13"

	actions: {
		// referential build for base python image
		python_pre_build: docker.#Build & {
			steps: [
				docker.#Pull & {
					source: "python:" + python_version
				},
				docker.#Run & {
					command: {
						name: "mkdir"
						args: ["/workdir"]
					}
				},
				docker.#Copy & {
					contents: client.filesystem."./".read.contents
					source:   "./pyproject.toml"
					dest:     "/workdir/pyproject.toml"
				},
				docker.#Copy & {
					contents: client.filesystem."./".read.contents
					source:   "./poetry.lock"
					dest:     "/workdir/poetry.lock"
				},
				docker.#Run & {
					workdir: "/workdir"
					command: {
						name: "pip"
						args: ["install", "--no-cache-dir", "poetry==" + poetry_version]
					}
				},
				docker.#Set & {
					config: {
						env: ["POETRY_VIRTUALENVS_CREATE"]: "false"
					}
				},
				docker.#Run & {
					workdir: "/workdir"
					command: {
						name: "poetry"
						args: ["install", "--no-interaction", "--no-ansi"]
					}
				},
			]
		}
		// python build for actions in this plan
		python_build: docker.#Build & {
			steps: [
				docker.#Copy & {
					input:    python_pre_build.output
					contents: client.filesystem."./".read.contents
					source:   "./"
					dest:     "/workdir"
				},
			]
		}
		// cuelang pre-build
		cue_pre_build: docker.#Build & {
			steps: [
				docker.#Pull & {
					source: "golang:latest"
				},
				docker.#Run & {
					command: {
						name: "mkdir"
						args: ["/workdir"]
					}
				},
				docker.#Run & {
					command: {
						name: "go"
						args: ["install", "cuelang.org/go/cmd/cue@latest"]
					}
				},
			]
		}
		// cue build for actions in this plan
		cue_build: docker.#Build & {
			steps: [
				docker.#Copy & {
					input:    cue_pre_build.output
					contents: client.filesystem."./".read.contents
					source:   "./project.cue"
					dest:     "/workdir/project.cue"
				},
			]
		}
		// applied code and/or file formatting
		clean: {
			// sort python imports with isort
			isort: docker.#Run & {
				input:   python_build.output
				workdir: "/workdir"
				command: {
					name: "poetry"
					args: ["run", "isort", "evap_or_ac/", "tests/"]
				}
			}
			// code style formatting with black
			black: docker.#Run & {
				input:   isort.output
				workdir: "/workdir"
				command: {
					name: "poetry"
					args: ["run", "black", "evap_or_ac/", "tests/"]
				}
				export: {
					directories: {
						"/workdir/evap_or_ac": _
						"/workdir/tests":      _
					}
				}
			}
			// code formatting for cuelang
			cue: docker.#Run & {
				input:   cue_build.output
				workdir: "/workdir"
				command: {
					name: "cue"
					args: ["fmt", "/workdir/project.cue"]
				}
				export: {
					files: "/workdir/project.cue": _
				}
			}
		}
		// lint
		lint: {
			// mypy static type check
			mypy: docker.#Run & {
				input:   python_build.output
				workdir: "/workdir"
				command: {
					name: "poetry"
					args: ["run", "mypy", "--ignore-missing-imports", "evap_or_ac/"]
				}
			}
			// isort (imports) formatting check
			isort: docker.#Run & {
				input:   mypy.output
				workdir: "/workdir"
				command: {
					name: "poetry"
					args: ["run", "isort", "--check", "--diff evap_or_ac/", "tests/"]
				}
			}
			// black formatting check
			black: docker.#Run & {
				input:   isort.output
				workdir: "/workdir"
				command: {
					name: "poetry"
					args: ["run", "black", "--check", "evap_or_ac/", "tests/"]
				}
			}
			// pylint checks
			pylint: docker.#Run & {
				input:   black.output
				workdir: "/workdir"
				command: {
					name: "poetry"
					args: ["run", "pylint", "evap_or_ac/", "tests/"]
				}
			}
			// bandit security vulnerabilities check
			bandit: docker.#Run & {
				input:   pylint.output
				workdir: "/workdir"
				command: {
					name: "poetry"
					args: ["run", "bandit", "-r", "evap_or_ac/"]
				}
			}
		}

	}
}
