#
# Copyright 2012-2013 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

import os.path
import contextlib
import errno
import logging

from testrunner import VdsmTestCase as TestCaseBase
from vdsm import utils
import time


class RetryTests(TestCaseBase):
    def testStopCallback(self):
        counter = [0]
        limit = 4

        def stopCallback():
            counter[0] += 1
            if counter[0] == limit:
                return True

            return False

        def foo():
            raise RuntimeError("If at first you don't succeed, try, try again."
                               "Then quit. There's no point in being a damn"
                               "fool about it.")
                               # W. C. Fields

        self.assertRaises(RuntimeError, utils.retry, foo, tries=(limit + 10),
                          sleep=0, stopCallback=stopCallback)
        # Make sure we had the proper amount of iterations before failing
        self.assertEquals(counter[0], limit)


class PidStatTests(TestCaseBase):
    def test(self):
        args = ["sleep", "3"]
        sproc = utils.execCmd(args, sync=False, sudo=False)
        stats = utils.pidStat(sproc.pid)
        pid = int(stats.pid)
        # procName comes in the format of (procname)
        name = stats.comm
        self.assertEquals(pid, sproc.pid)
        self.assertEquals(name, args[0])
        sproc.kill()
        sproc.wait()


class CommandPathTests(TestCaseBase):
    def testExisting(self):
        cp = utils.CommandPath('sh', 'utter nonsense', '/bin/sh')
        self.assertEquals(cp.cmd, '/bin/sh')

    def testMissing(self):
        NAME = 'nonsense'
        try:
            utils.CommandPath(NAME, 'utter nonsense').cmd
        except OSError as e:
            self.assertEquals(e.errno, errno.ENOENT)
            self.assertIn(NAME, e.strerror)


class GeneralUtilsTests(TestCaseBase):
    def testPanic(self):
        self.assertRaises(AssertionError, utils.panic, "panic test")

    def testAnyFnmatch(self):
        self.assertTrue(utils.anyFnmatch('test1', ['test0', 'test1']))

    def testReadMemInfo(self):
        meminfo = utils.readMemInfo()
        # most common fields as per man 5 proc
        # add your own here
        fields = ('MemTotal', 'MemFree', 'Buffers', 'Cached', 'SwapCached',
                  'Active', 'Inactive', 'SwapTotal', 'SwapFree', 'Dirty',
                  'Writeback', 'Mapped', 'Slab', 'VmallocTotal',
                  'VmallocUsed', 'VmallocChunk')
        for field in fields:
            self.assertIn(field, meminfo)
            self.assertTrue(isinstance(meminfo[field], int))

    def testParseMemInfo(self):
        testPath = os.path.realpath(__file__)
        dirName = os.path.dirname(testPath)
        path = os.path.join(dirName, "mem_info.out")
        with open(path) as f:
            meminfo = utils._parseMemInfo(f.readlines())
        # testing some random fields
        self.assertEquals(meminfo['NFS_Unstable'], 0)
        self.assertEquals(meminfo['KernelStack'], 2760)
        self.assertEquals(meminfo['Inactive'], 1432748)

    def testGrouper(self):
        iterable = '1234567890'
        grouped = [('1', '2'), ('3', '4'), ('5', '6'), ('7', '8'), ('9', '0')]
        self.assertEquals(list(utils.grouper(iterable, 2)), grouped)

        iterable += 'a'
        grouped.append(('a', None))
        self.assertEquals(list(utils.grouper(iterable, 2)), grouped)

        iterable += 'bcde'
        grouped = [('1', '2', '3'), ('4', '5', '6'), ('7', '8', '9'),
                   ('0', 'a', 'b'), ('c', 'd', 'e')]
        self.assertEquals(list(utils.grouper(iterable, 3)), grouped)

        grouped = [('1', '2', '3', '4', '5'), ('6', '7', '8', '9', '0'),
                   ('a', 'b', 'c', 'd', 'e')]
        self.assertEquals(list(utils.grouper(iterable, 5)), grouped)


class AsyncProcessOperationTests(TestCaseBase):
    def _echo(self, text):
        proc = utils.execCmd(["echo", "-n", "test"], sync=False)

        def parse(rc, out, err):
            return out

        return utils.AsyncProcessOperation(proc, parse)

    def _sleep(self, t):
        proc = utils.execCmd(["sleep", str(t)], sync=False)
        return utils.AsyncProcessOperation(proc)

    def _fail(self, t):
        proc = utils.execCmd(["sleep", str(t)], sync=False)

        def parse(rc, out, err):
            raise Exception("TEST!!!")

        return utils.AsyncProcessOperation(proc, parse)

    def test(self):
        aop = self._sleep(1)
        self.assertEquals(aop.result(), ((0, "", ""), None))

    def testAlreadyExitedSuccess(self):
        aop = self._sleep(0)
        time.sleep(1)
        self.assertEquals(aop.result(), ((0, "", ""), None))

    def testAlreadyExitedFail(self):
        aop = self._sleep("hello")
        time.sleep(1)
        ((rc, out, err), err) = aop.result()
        self.assertEquals(err, None)
        self.assertEquals(rc, 1)

    def testWait(self):
        aop = self._sleep(1)
        aop.wait(timeout=2)

    def testParser(self):
        aop = self._echo("test")
        self.assertEquals(aop.result(), ("test", None))

    def testStop(self):
        aop = self._sleep(10)
        aop.stop()

        start = time.time()
        aop.result()
        end = time.time()
        duration = end - start
        self.assertTrue(duration < 2)

    def testException(self):
        aop = self._fail(1)
        res, err = aop.result()
        self.assertEquals(res, None)
        self.assertNotEquals(err, None)


class CallbackChainTests(TestCaseBase):
    def testCanPassIterableOfCallbacks(self):
        f = lambda: False
        callbacks = [f] * 10
        chain = utils.CallbackChain(callbacks)
        self.assertEqual(list(chain.callbacks), callbacks)

    def testEmptyChainIsNoop(self):
        chain = utils.CallbackChain()
        self.assertFalse(chain.callbacks)
        chain.start()
        chain.join()
        # assert exception isn't thrown in start on empty chain

    def testAllCallbacksAreInvokedIfTheyReturnFalse(self):
        n = 10
        counter = [n]

        def callback():
            counter[0] -= 1
            return False

        chain = utils.CallbackChain([callback] * n)
        chain.start()
        chain.join()
        self.assertEqual(counter[0], 0)

    def testChainStopsAfterSuccessfulCallback(self):
        n = 10
        counter = [n]

        def callback():
            counter[0] -= 1
            return counter[0] == 5

        chain = utils.CallbackChain([callback] * n)
        chain.start()
        chain.join()
        self.assertEquals(counter[0], 5)

    def testArgsPassedToCallback(self):
        callbackArgs = ('arg', 42, 'and another')
        callbackKwargs = {'some': 42, 'kwargs': []}

        def callback(*args, **kwargs):
            self.assertEqual(args, callbackArgs)
            self.assertEqual(kwargs, callbackKwargs)

        chain = utils.CallbackChain()
        chain.addCallback(callback, *callbackArgs, **callbackKwargs)
        chain.start()
        chain.join()


@contextlib.contextmanager
def loghandler(handler, logger=""):
    log = logging.getLogger(logger)
    log.addHandler(handler)
    try:
        yield {}
    finally:
        log.removeHandler(handler)


class TracebackTests(TestCaseBase):

    def __init__(self, *a, **kw):
        self.record = None
        super(TestCaseBase, self).__init__(*a, **kw)

    def testDefaults(self):
        @utils.traceback()
        def fail():
            raise Exception
        with loghandler(self):
            self.assertRaises(Exception, fail)
        self.assertEquals(self.record.name, "root")
        self.assertTrue(self.record.exc_text is not None)

    def testOn(self):
        logger = "test"

        @utils.traceback(on=logger)
        def fail():
            raise Exception
        with loghandler(self, logger=logger):
            self.assertRaises(Exception, fail)
        self.assertEquals(self.record.name, logger)

    def testMsg(self):
        @utils.traceback(msg="WAT")
        def fail():
            raise Exception
        with loghandler(self):
            self.assertRaises(Exception, fail)
        self.assertEquals(self.record.message, "WAT")

    # Logging handler interface

    level = logging.DEBUG

    def acquire(self):
        pass

    def release(self):
        pass

    def handle(self, record):
        assert self.record is None
        self.record = record


class RollbackContextTests(TestCaseBase):

    class UndoException(Exception):
        """A special exception for testing exceptions during undo functions"""

    class OriginalException(Exception):
        """A special exception for testing exceptions in the with statement"""

    def setUp(self):
        self._called = 0

    def _callDef(self):
        self._called += 1
        self.log.info("Incremented call count (%d)", self._called)

    def _raiseDef(self, ex=Exception()):
        self.log.info("Raised exception (%s)", ex.__class__.__name__)
        raise ex

    def test(self):
        with utils.RollbackContext() as rollback:
            rollback.prependDefer(self._callDef)

        self.assertEquals(self._called, 1)

    def testRaise(self):
        """
        Test that raising an exception in a deferred action does
        not block all subsequent actions from running
        """
        try:
            with utils.RollbackContext() as rollback:
                rollback.prependDefer(self._callDef)
                rollback.prependDefer(self._raiseDef)
                rollback.prependDefer(self._callDef)
        except Exception:
            self.assertEquals(self._called, 2)
            return

        self.fail("Exception was not raised")

    def testFirstUndoException(self):
        """
        Test that if multiple actions raise an exception only the first one is
        raised. When performing a batch rollback operations, probably the first
        exception is the root cause.
        """
        try:
            with utils.RollbackContext() as rollback:
                rollback.prependDefer(self._callDef)
                rollback.prependDefer(self._raiseDef)
                rollback.prependDefer(self._callDef)
                rollback.prependDefer(self._raiseDef, RuntimeError())
                rollback.prependDefer(self._callDef)
        except RuntimeError:
            self.assertEquals(self._called, 3)
            return
        except Exception:
            self.fail("Wrong exception was raised")

        self.fail("Exception was not raised")

    def testKeyError(self):
        """
        KeyError is raised as a tuple and not expection. Re-raising it
        should be aware of this fact and handled carfully.
        """
        try:
            with utils.RollbackContext():
                {}['aKey']
        except KeyError:
            return
        except Exception:
            self.fail("Wrong exception was raised")

        self.fail("Exception was not raised")

    def testPreferOriginalException(self):
        """
        Test that if an exception is raised both from the with
        statement and from the finally clause, the one from the with
        statement is the one that's actually raised.
        More info in: http://docs.python.org/
        2.6/library/stdtypes.html#contextmanager.__exit__
        """
        try:
            with utils.RollbackContext() as rollback:
                rollback.prependDefer(self._raiseDef, self.UndoException())
                raise self.OriginalException()
        except self.OriginalException:
            return
        except self.UndoException:
            self.fail("Wrong exception was raised - from undo function. \
                        should have re-raised OriginalException")
        except Exception:
            self.fail("Wrong exception was raised")

        self.fail("Exception was not raised")
