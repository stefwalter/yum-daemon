Name:           yumdaemon
Version:        0.1
Release:        0.1%{?dist}
Summary:        Dbus daemon for yum package actions

License:        GPL2+
URL:            https://github.com/timlau/yum-daemon
Source0:        yumdaemon-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python2-devel
Requires:       dbus-python
Requires:       yum >= 3.4.0
Requires:       polkit

%description
Dbus daemon for yum package actions

%prep
%setup -q


%build
# Nothing to build

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT

%package -n python3-%{name}
Summary:        Python 3 api for communicating with the yum-daemon DBus service
Group:          Applications/System
BuildRequires:  python3-devel
Requires:       %{name} = %{version}-%{release}
Requires:       gobject-introspection

%description -n python3-%{name}
Python 3 api for communicating with the yum-daemon DBus service


%files -n  python3-%{name}
%{python3_sitelib}/%{name}/*

%package -n python-%{name}
Summary:        Python 2 api for communicating with the yum-daemon DBus service
Group:          Applications/System
BuildRequires:  python2-devel
Requires:       %{name} = %{version}-%{release}

%description -n python-%{name}
Python 2 api for communicating with the yum-daemon DBus service


%files -n  python-%{name}
%{python_sitelib}/%{name}/*

%files
%doc README.md examples/
%{_datadir}/dbus-1/system-services/*
%{_datadir}/%{name}/*
%{_datadir}/polkit-1/actions
%{_sysconfdir}//dbus-1/system.d/*


%changelog
* Sat May 26 2012 Tim Lauridsen <timlau@fedoraproject.org> 0.1-0.1
- Initial rpm for yum-daemon