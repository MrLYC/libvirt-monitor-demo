#!/usr/bin/env python
# encoding: utf-8

from contextlib import closing
from xml.etree import ElementTree
from itertools import repeat
from collections import namedtuple, OrderedDict

import libvirt


def connection():
    return closing(libvirt.open('qemu:///system'))


class Plugin(list):
    def register(self, function):
        self.append(function)
        return function


class Monitor(object):
    PluginContext = namedtuple("PluginContext", [
        "domain", "uuid", "xml_desc",
    ])
    plugins = Plugin()

    def __init__(self, uuid):
        self.uuid = uuid

    @plugins.register
    def _vm_info(context):
        domain = context.domain
        xml_desc = context.xml_desc
        return {
            "id": xml_desc.get("id"),
            "uuid": xml_desc.find("uuid").text,
            "name": xml_desc.find("name").text,
            "type": xml_desc.get("type"),
        }

    @plugins.register
    def _cpu_stats(context):
        domain = context.domain
        cpu_stat_lst = domain.getCPUStats(True)
        if not cpu_stat_lst:
            cpu_stats = {}
        else:
            cpu_stats = cpu_stat_lst[0]

        return {
            "cpu.vcpu.count": domain.vcpusFlags(),
            "cpu.time": cpu_stats.get("cpu_time"),
            "cpu.time.system": cpu_stats.get("system_time"),
            "cpu.time.user": cpu_stats.get("user_time"),
        }

    @plugins.register
    def _mem_stats(context):
        mem_stats = context.domain.memoryStats()
        return {
            "mem.rss": mem_stats.get("rss"),
            "mem.actual": mem_stats.get("actual"),
            "mem.actual.balloon": mem_stats.get("actual_balloon"),
            "mem.unused": mem_stats.get("unused"),
            "mem.available": mem_stats.get("available"),
            "mem.swap.in": mem_stats.get("swap_in"),
            "mem.swap.out": mem_stats.get("swap_out"),
            "mem.fault.major": mem_stats.get("major_fault"),
            "mem.fault.minor": mem_stats.get("minor_fault"),
        }

    @plugins.register
    def _interface_stats(context):
        domain = context.domain
        iface = context.xml_desc.find("devices/interface/target").get("dev", "")
        stats = iter(domain.interfaceStats(iface) if iface else repeat(None, 8))
        return {
            "iface[%s].read.bytes" % iface: next(stats),
            "iface[%s].read.packets" % iface: next(stats),
            "iface[%s].read.errors" % iface: next(stats),
            "iface[%s].read.drops" % iface: next(stats),
            "iface[%s].write.bytes" % iface: next(stats),
            "iface[%s].write.packets" % iface: next(stats),
            "iface[%s].write.errors" % iface: next(stats),
            "iface[%s].write.drops" % iface: next(stats),
        }

    @plugins.register
    def _disk_stats(context):
        domain = context.domain
        disk = context.xml_desc.find("devices/disk/target").get("dev", "")
        stats = iter(domain.blockStats(disk) if disk else repeat(None, 5))
        return {
            "disk[%s].read.requests" % disk: next(stats),
            "disk[%s].read.bytes" % disk: next(stats),
            "disk[%s].write.requests" % disk: next(stats),
            "disk[%s].write.bytes" % disk: next(stats),
            "disk[%s].errors" % disk: next(stats),
        }

    def __call__(self):
        with connection() as conn:
            domain = conn.lookupByUUIDString(self.uuid)
            result = OrderedDict()
            context = self.PluginContext(
                uuid=self.uuid, domain=domain,
                xml_desc=ElementTree.fromstring(domain.XMLDesc()),
            )
            for p in self.plugins:
                result.update(p(context))
        return result


if __name__ == "__main__":
    import sys

    monitor = Monitor(sys.argv[1])
    data = monitor()
    for k, v in data.items():
        print k, v
