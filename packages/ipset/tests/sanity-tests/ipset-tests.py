#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1+
# ~~~
#   Description: Tests for ipset
#
#   Author: Susant Sahani <susant@redhat.com>
#   Copyright (c) 2018 Red Hat, Inc.
# ~~~

import errno
import os
import sys
import time
import unittest
import subprocess
import signal
import shutil
import socket
from pyroute2 import IPRoute

def setUpModule():

    if shutil.which('ipset') is None:
        raise OSError(errno.ENOENT, 'ipset not found')

    if shutil.which('iperf3') is None:
        raise OSError(errno.ENOENT, 'iperf3 not found')

def tearDownModule():
    pass

class GenericUtilities():

    def SetupVethInterface(self):

        ip = IPRoute()

        ip.link('add', ifname='veth-test', peer='veth-peer', kind='veth')
        idx_veth_test = ip.link_lookup(ifname='veth-test')[0]
        idx_veth_peer = ip.link_lookup(ifname='veth-peer')[0]

        ip.link('set', index=idx_veth_test, address='02:01:02:03:04:08')
        ip.link('set', index=idx_veth_peer, address='02:01:02:03:04:09')

        ip.addr('add', index=idx_veth_test, address='192.168.225.32', mask=24)
        ip.addr('add', index=idx_veth_peer, address='192.168.225.33', mask=24)

        ip.link('set', index=idx_veth_test, state='up')
        ip.link('set', index=idx_veth_peer, state='up')

        ip.close()

    def TearDownVethInterface(self):

        ip = IPRoute()
        ip.link('del', index=ip.link_lookup(ifname='veth-test')[0])
        ip.close()

    def AddAddress(self, interface, address):
        ip = IPRoute()

        idx_veth_peer = ip.link_lookup(ifname=interface)[0]
        ip.close()

    def IPSetAdd(self, hashset, address):
        subprocess.check_output(['ipset', 'add', hashset, address])

    def IPSetRemove(self, hashset, address):
        subprocess.check_output(['ipset', 'del', hashset, address])

    def IPSetCreateHashSet(self, hashset, hashtype):
        subprocess.check_output(['ipset', 'create', hashset, hashtype])

    def IPSetDestroyHashSet(self, hashset):
        subprocess.check_output(['ipset', 'destroy', hashset])

class IpsetTests(unittest.TestCase, GenericUtilities):

    def setUp(self):
        self.SetupVethInterface()

    def tearDown(self):
        self.TearDownVethInterface()

    def test_ipset_bitmap_ip_netfilter(self):

        self.IPSetCreateHashSet('testnetiperf', 'hash:ip')

        self.IPSetAdd('testnetiperf', '192.168.225.32')
        self.IPSetAdd('testnetiperf', '192.168.225.33')

        subprocess.check_output(['ipset', 'test','testnetiperf','192.168.225.32'])
        subprocess.check_output(['ipset', 'test','testnetiperf','192.168.225.33'])

        subprocess.check_output(['systemctl', 'start', 'iperf3d.service'])
        time.sleep(5)

        r = subprocess.call("iperf3" + " -c 192.168.225.32 -p 55555 --connect-timeout 5", shell=True)
        self.assertEqual(r, 0)

        r = subprocess.call("iptables" +  " -I INPUT -m set --match-set testnetiperf src -j DROP", shell=True)
        self.assertEqual(r, 0)

        r = subprocess.call("iperf3" + " -c 192.168.225.32 -p 55555 --connect-timeout 5", shell=True)
        self.assertNotEqual(r, 0)

        subprocess.check_output(['systemctl', 'stop', 'iperf3d.service'])

        subprocess.call("iptables" + " --delete INPUT -m set --match-set testnetiperf src -j DROP" , shell=True)

        self.IPSetDestroyHashSet('testnetiperf')

    def test_ipset_add_bitmap_ip(self):

        self.IPSetCreateHashSet('testnet', 'hash:ip')

        self.IPSetAdd('testnet', '192.168.11.12')
        self.IPSetAdd('testnet', '192.168.11.13')
        self.IPSetAdd('testnet', '192.168.11.14')
        self.IPSetAdd('testnet', '192.168.11.15')

        subprocess.check_output(['ipset', 'test','testnet','192.168.11.12'])
        subprocess.check_output(['ipset', 'test','testnet','192.168.11.13'])
        subprocess.check_output(['ipset', 'test','testnet','192.168.11.14'])
        subprocess.check_output(['ipset', 'test','testnet','192.168.11.15'])

        self.IPSetDestroyHashSet('testnet')

    def test_ipset_delete_bitmap_ip(self):

        self.IPSetCreateHashSet('testnet', 'hash:ip')

        self.IPSetAdd('testnet', '192.168.11.12')
        self.IPSetAdd('testnet', '192.168.11.13')

        subprocess.check_output(['ipset', 'test','testnet','192.168.11.12'])
        subprocess.check_output(['ipset', 'test','testnet','192.168.11.13'])

        self.IPSetRemove('testnet', '192.168.11.12')

        r = subprocess.call("ipset" + " test testnet 192.168.11.12", shell=True)
        self.assertEqual(r, 1)

        self.IPSetDestroyHashSet('testnet')

    def test_ipset_hash_bitmap_mac(self):

        self.IPSetCreateHashSet('testmac', 'hash:mac')

        self.IPSetAdd('testmac', '02:01:02:03:04:09')

        subprocess.check_output(['ipset', 'test','testmac','02:01:02:03:04:09'])

        self.IPSetRemove('testmac', '02:01:02:03:04:09')

        r = subprocess.call("ipset" + " test testmac 02:01:02:03:04:09", shell=True)
        self.assertEqual(r, 1)

        self.IPSetDestroyHashSet('testmac')

    def test_ipset_hash_bitmap_ipport(self):

        self.IPSetCreateHashSet('testipport', 'hash:ip,mac')

        self.IPSetAdd('testipport', '1.1.1.1,02:01:02:03:04:09')

        subprocess.check_output(['ipset', 'test','testipport','1.1.1.1,02:01:02:03:04:09'])

        self.IPSetRemove('testipport', '1.1.1.1,02:01:02:03:04:09')

        r = subprocess.call("ipset" + " test testipport 1.1.1.1,02:01:02:03:04:09", shell=True)
        self.assertEqual(r, 1)

        self.IPSetDestroyHashSet('testipport')

    def test_ipset_hash_bitmap_ipport(self):

        self.IPSetCreateHashSet('testipport', 'hash:ip,port')

        self.IPSetAdd('testipport', '192.168.1.1,udp:53')
        self.IPSetAdd('testipport', '192.168.1.1,5555')

        subprocess.check_output(['ipset', 'test','testipport','192.168.1.1,udp:53'])
        subprocess.check_output(['ipset', 'test','testipport','192.168.1.1,5555'])

        self.IPSetRemove('testipport', '192.168.1.1,5555')

        r = subprocess.call("ipset" + " test testipport 192.168.1.1,5555", shell=True)
        self.assertEqual(r, 1)

        self.IPSetDestroyHashSet('testipport')

    def test_ipset_hash_bitmap_ipportip(self):

        self.IPSetCreateHashSet('testipportip', 'hash:ip,port,ip')

        self.IPSetAdd('testipportip', '192.168.1.1,80,10.0.0.1')
        self.IPSetAdd('testipportip', '192.168.1.2,80,10.0.0.2')

        subprocess.check_output(['ipset', 'test','testipportip','192.168.1.1,80,10.0.0.1'])
        subprocess.check_output(['ipset', 'test','testipportip','192.168.1.1,80,10.0.0.1'])

        self.IPSetRemove('testipportip', '192.168.1.1,80,10.0.0.1')

        r = subprocess.call("ipset" + " test testipportip 192.168.1.1,80,10.0.0.1", shell=True)
        self.assertEqual(r, 1)

        self.IPSetDestroyHashSet('testipportip')

    def test_ipset_hash_bitmap_netiface(self):

        self.IPSetCreateHashSet('testnetiface', 'hash:net,iface')

        self.IPSetAdd('testnetiface', '192.168.0/24,veth-test')
        self.IPSetAdd('testnetiface', '192.167.0/24,veth-peer')

        subprocess.check_output(['ipset', 'test','testnetiface','192.168.0/24,veth-test'])
        subprocess.check_output(['ipset', 'test','testnetiface','192.167.0/24,veth-peer'])

        self.IPSetRemove('testnetiface', '192.168.0/24,veth-test')

        r = subprocess.call("ipset" + " test testnetiface 192.168.0/24,veth-test", shell=True)
        self.assertEqual(r, 1)

        self.IPSetDestroyHashSet('testnetiface')

if __name__ == '__main__':
        unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=3))
