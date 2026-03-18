# vim: filetype=spec

%define version @@@Version@@@
%define builddir %{_builddir}/postfix-logsums-%{version}

Name:           postfix-logsums
Version:        %{version}
Release:        @@@Release@@@%{?dist}
Summary:        A log analyzer/summarizer for the Postfix MTA.

Group:          Development/Languages/Python
License:        LGPL-3
Distribution:   Frank Brehm
URL:            https://github.com/pixelpark/postfix-logsums
Source0:        postfix-logsums.%{version}.tar.gz

BuildRequires:	gettext
BuildRequires:  python%{python3_pkgversion}
BuildRequires:  python%{python3_pkgversion}-babel
BuildRequires:  python%{python3_pkgversion}-devel
BuildRequires:  python%{python3_pkgversion}-libs
BuildRequires:  python%{python3_pkgversion}-fb-logging >= 1.0.0
BuildRequires:  python%{python3_pkgversion}-pyyaml
BuildRequires:  python%{python3_pkgversion}-semver
BuildRequires:  pyproject-rpm-macros

Requires:       python%{python3_pkgversion}
Requires:       python%{python3_pkgversion}-babel
Requires:       python%{python3_pkgversion}-libs
Requires:       python%{python3_pkgversion}-pyyaml
Requires:       python%{python3_pkgversion}-semver
BuildArch:      noarch

%description
A log analyzer/summarizer for the Postfix MTA.
It provides both a Python module postfix_logsums as well
as the executable script postfix-logsums based on the
latter module. The Python module may be used as an API.

This package provides the following script:
 * postfix-logsums - The executable script for analyzing Postfix logs.

This is the Python@@@py_version_nodot@@@ version.

%prep
echo "Preparing '${builddir}-' ..."
echo "Pwd: $( pwd )"
%autosetup -p1 -v

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files postfix_logsums

echo "Whats in '%{builddir}':"
ls -lA '%{builddir}'

echo "Whats in '%{buildroot}':"
ls -lA '%{buildroot}'

%files -f %{pyproject_files}
%defattr(-,root,root,-)
%license LICENSE
%doc LICENSE README.md CHANGELOG.md debian/changelog pyproject.toml
%{_bindir}/*
%{_datadir}/*

%changelog
