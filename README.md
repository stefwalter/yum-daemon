Simple prof of concept for a dbus based yum daemon


How to install:
================
Run the following as root

  make install

How to test:
=============
just run:
  
su -c "make test-verbose"

to run the unit test with output to console

or 

su -c "make test" to just run the unit tests    
  
to make the daemon exit run:

  python client.py quit 
  
if you want to monitor the yum progress signals send by the daemon
the start the following in another shell window.

python monitor.py
  
If you run it as normal user, you well get PolicyKit dialog asking for root password
If you run as root it will just execute

If you want to test the the daemon without installing it:
su -c "python daemon.py"

in a separate shell window.