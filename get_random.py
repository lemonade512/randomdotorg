import requests
import datetime
from threading import Lock

# TODO add checks for errors (code other than 200)
# TODO implement error checking when requesting more than 10,000 numbers
# TODO should all methods that send a request start with 'request'?

#If you use an automated client, please make sure it observes
#the following guidelines:
#
# 1) Do not issue multiple simultaneous requests. If you use a
#single-threaded client, this will not be any concern for you.
#If you use a multithreaded client, use a locking scheme to
#prevent your client from issuing multiple simultaneous requests.
#
# 2) If you need many numbers, issue requests that fetch the numbers
#in blocks as large as possible. Please do not issue a request
#for every single number, unless you only need one.
#
# 3) Use a long timeout value for your requests. Unless you have
# used up your quota, the RANDOM.ORG server actually tries to
# satisfy all requests, so if you use a short timeout value,
# your request will be abandoned halfways and the numbers discarded.
# This increases load on the server. Allow at least a couple of
# minutes for the server to complete your request.
#
# 4) Configure your client to examine your remaining quota at regular
# intervals. If your allowance is negative, your client should back
# off and not issue any requests for numbers for a while. See the
# Quota Checker Documentation for details on how to do this, how long
# to delay, etc.
#
# 5) Configure your client to supply your email address in the User
# Agent field of the request. That way, I can drop you a line if your
# client is causing trouble.

class QuotaError(Exception):
    pass

class TrueRandom(object):
    USER_EMAIL = 'philliplemons512@gmail.com'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_EMAIL})
        self.timeout = 60 * 3 # timeout is in seconds (3 minutes)

        # Wait time is in seconds
        self.wait_time = 0
        # Last attempt time is stored as a datetime object
        self.last_attempt_time = None
        self.waiting = False

        self.lock = Lock()
        self._stored_ints = []

    def request_new_ints(self, num):
        """ Requests a list of ints that will be stored and used by _randbelow instead
        of sending requests to random.org. This allows the client to limit the number
        of requests to the random.org servers. """
        raise NotImplementedError

    def getrandbits(self, bits, num=1):
        """ Returns a list of numbers between 0 and 2^n - 1 where n is the number of bits. """
        if bits != int(bits):
            raise ValueError('Non-integer bits used in getrandbits()')

        return self._randbelow(2**bits, num)

    def randrange(self, start, stop=None, step=1, num=1):
        """ Choose a random item from range(start, stop[, step]).

        Code lifted from random.py
        """
        istart = int(start)
        if istart != start:
            raise ValueError("Non-integer arg 1 for randrange()")
        if stop is None:
            if istart > 0:
                return self._randbelow(istart, num)
            raise ValueError("empty range for randrange()")

        # stop argument supplied
        istop = int(stop)
        if istop != stop:
            raise ValueError("Non-integer arg 2 for randrange()")
        width = istop - istart
        if step == 1 and width > 0:
            return istart + self._randbelow(width, num)
        if step == 1:
            raise ValueError("empty range for randrange() (%d, %d, %d)" %(istart, istop, width))

        # Non-unit step argument supplied
        istep = int(step)
        if istep != step:
            raise ValueError("Non-integer, stop for randrange()")
        if istep > 0:
            n = (width + istep - 1) // istep
        elif istep < 0:
            n = (width + istep + 1) // istep
        else:
            raise ValueError("zero step for randrange()")

        if n <= 0:
            raise ValueError("empty range for randrange()")

        return istart + istep*self._randbelow(n, num)

    def randint(self, a, b, num=1):
        """ Return random integer in range [a, b], including both end points. """
        return self.randrange(a, b+1, num=1)

    def choice(self, seq):
        """ Chooses a random element from a list. """
        try:
            i = self._randbelow(len(seq))
        except ValueError:
            raise IndexError("Cannot choose from an empty sequence.")
        return seq[i]

    def shuffle(self, seq):
        """ Takes a list and randomly shuffles it. """
        #TODO find a way to test this method (possibly without actually using your quota)
        rand_indices = self._randsequence(0, len(seq)-1)
        for i in xrange(len(seq)-1):
            j = rand_indices[i]
            seq[i], seq[j] = seq[j], seq[i]

    def sample(self, pop, k):
        """ Takes k random, unique elements from the population.

        If the population contains repeats then each occurence is a possible
        selection in the sample.

        Args:
            pop: The list, set or sequence to take a sample from
            k: The size of the sample you want to take

        Returns:
            A new list containing k elements from the population. The original
            population is unchanged.
        """
        raise NotImplementedError

    def reportquota(self):
        quota = self._request_quota()
        print "This IP address currently has a quota of " + str(quota) + " bits"

    def _randsequence(self, start, stop=None):
        """ Returns a list of numbers from start to stop in random order. """
        #TODO raise errors if start or stop are not integers
        self.lock.acquire()
        url = 'http://www.random.org/sequences/'
        if stop == None:
            url += '?min=0&max=' + str(start)
        else:
            url += '?min=' + str(start) + '&max=' + str(stop)
        url += '&format=plain&rand=new&col=1'
        response = self.session.get(url, timeout=self.timeout)
        self.lock.release()
        return [int(i) for i in response.text.split()]

    def _randbelow(self, n, num=1):
        """ Returns a list of integers in the range [0, n) """
        #NOTE max allowed to get is 10,000
        #NOTE min and max allowed numbers are [-1e9, 1e9]
        self.lock.acquire()
        if n != int(n):
            raise ValueError('Non-integer n used in _randbelow()')
        if n == 0:
            raise ValueError('Cannot get a number below 0')
        if num != int(num):
            raise ValueError('Non-integer num used in _randbelow()')

        url = 'http://www.random.org/integers/'
        url += '?num='+str(num)
        url += '&min=0'
        url += '&max='+str(n-1)
        url += '&col=1&base=10&format=plain&rnd=new'
        response = self.session.get(url, timeout=self.timeout)
        self.lock.release()
        return [int(i) for i in response.text.split()]

    def _request_quota(self):
        """ Sends a request to random.org to get the remaining daily bit quota. """
        self.lock.acquire()
        url = 'http://www.random.org/quota/?format=plain'
        response = self.session.get(url, timeout=self.timeout)
        self.lock.release()
        return int(response.text)

    def checkquota(self):
        if self.waiting:
            # Time since last attempt
            t_delta_sec = (datetime.datetime.now() - self.last_attempt_time).seconds
            if t_delta_sec < self.wait_time:
                # We are waiting. Please try again later
                raise QuotaError()

        quota = self._request_quota()

        if quota < 1:
            if not self.waiting:
                self.waiting = True
            self.last_attempt_time = int(datetime.datetime.now())
            self.attempts += 1
            # exponential backoff with a max of 24 hours TODO add ability to reset at midnight
            self.wait_time = min((2**self.attempts - 1) * 60, 60*60*24)
            raise QuotaError()
        else:
            self.waiting = False
            self.wait_time = 0
            self.attempts = 0

if __name__ == "__main__":
    t = TrueRandom()
    #t.request_sequence()
    #print t.request_new_ints()
    t.reportquota()
    #print t.getrandbits(5)
    #print t.request_new_ints()
    #t.reportquota()

