# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-03-17

### Added

* Adding CHANGELOG.md.
* Adding minimized setup.cfg.
* Adding entrypoint postfix-logsums in `src/postfix_logsums/app.py`.

### Changed

* Renaming `test/` => `tests/`
* Moving `postfix_logsums/` => `src/postfix_logsums/`
* Refactoring testing scripts.
* Updating update-env.sh for refactored virtual env.
* Updating xtract-xlate-msgs.sh and etc/babel.ini.
* Refactoring `src/postfix_logsums/xlate.py`.

### Fixed

* Fixing many linting errors.

### Removed

* Removing get-debian-release, get-debian-version, get-rpm-release, get-rpm-version,
  postfix-logsums, requirements.txt, setup.cfg and setup.py.

## [0.9.4] - 2023-05-09

### Changed

* Changing dependencies of generated RPM files.

## [0.9.3] - 2023-04-20

### Added

* Adding .gitlab-ci.yml for having CI jobs also in Gitlab.

## [0.9.2] - 2023-04-20

### Fixed

* Fixing translations.

## [0.9.1] - 2023-04-19

### Changed

* Generating .mo-files on building Python package.

## [0.9.0] - 2023-04-19

### Changed

* Making cmd line option 'day' able to get a prticular date in ISO format.
* Finishing translations.

## [0.8.1] - 2023-03-31

### Added

* Adding `postfix_logsums/xlate.py` and helper scripts for localisation.
* Adding translation files (\*.pot and \*.po) below `locale/`.
* Adding Translating massages in `postfix_logsums/__init__.py`,
  `postfix_logsums/errors.py` and `postfix_logsums/stats.py`.

## [0.8.0] - 2023-03-27

### Added

* Adding all files for building Debian packages.
* Adding all files for building RPM packages.

### Changed

* Extending Github workflow by jobs for building and deploying Debian and RPM packages.

## [0.7.8] - 2023-03-27

### Added

* Adding first usable stuff

## [0.1.0] - 2023-02-18

### Added 

* Initial release

[Unreleased]: https://github.com/pixelpark/postfix-logsums/compare/0.9.4...pyproject
[0.9.4]: https://github.com/pixelpark/postfix-logsums/compare/0.9.3...0.9.4
[0.9.3]: https://github.com/pixelpark/postfix-logsums/compare/0.9.2...0.9.3
[0.9.2]: https://github.com/pixelpark/postfix-logsums/compare/0.9.1...0.9.2
[0.9.1]: https://github.com/pixelpark/postfix-logsums/compare/0.9.0...0.9.1
[0.9.0]: https://github.com/pixelpark/postfix-logsums/compare/0.8.1...0.9.0
[0.8.1]: https://github.com/pixelpark/postfix-logsums/compare/0.8.0...0.8.1
[0.8.0]: https://github.com/pixelpark/postfix-logsums/compare/0.7.8...0.8.0
[0.7.8]: https://github.com/pixelpark/postfix-logsums/compare/0.1.0...0.7.8
[0.1.0]: https://github.com/pixelpark/postfix-logsums/tree/0.1.0
