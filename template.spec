%define version @@@Version@@@
%define builddir postfix-logsums-%{version}

Name:           postfix-logsums
Version:        %{version}
Release:        @@@Release@@@%{?dist}
Summary:        A log analyzer/summarizer for the Postfix MTA.

Group:          Development/Languages/Python
License:        LGPL-3
Distribution:   Frank Brehm
URL:            https://github.com/pixelpark/postfix-logsums
Source0:        postfix-logsums.%{version}.tar.gz

BuildRequires:  python@@@py_version_nodot@@@
BuildRequires:  python@@@py_version_nodot@@@-libs
BuildRequires:  python@@@py_version_nodot@@@-devel
BuildRequires:  python@@@py_version_nodot@@@-setuptools
BuildRequires:  python@@@py_version_nodot@@@-babel
BuildRequires:  python@@@py_version_nodot@@@-fb-logging >= 0.5.0
Requires:       python@@@py_version_nodot@@@
Requires:       python@@@py_version_nodot@@@-libs
Requires:       python@@@py_version_nodot@@@-babel
Requires:       python@@@py_version_nodot@@@-pyyaml
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
%setup -n %{builddir}

%build
cd ../%{builddir}
python@@@py_version_dot@@@ setup.py build

%install
cd ../%{builddir}
echo "Buildroot: %{buildroot}"
python@@@py_version_dot@@@ setup.py install --prefix=%{_prefix} --root=%{buildroot}

%files
%defattr(-,root,root,-)
%license LICENSE
%doc LICENSE README.md requirements.txt debian/changelog
%{_bindir}/*
%{python3_sitelib}/*

%changelog
