import pytest

from clikit.api.io.flags import VERBOSE
from clikit.io.buffered_io import BufferedIO
from clikit.ui.components.exception_trace import ExceptionTrace
from clikit.utils._compat import PY2
from clikit.utils._compat import PY36
from clikit.utils._compat import PY38


def fail():
    raise Exception("Failed")


@pytest.mark.skipif(PY36, reason="Legacy error messages are Python <3.6 only")
def test_render_legacy_error_message():
    io = BufferedIO()

    try:
        raise Exception("Failed")
    except Exception as e:
        trace = ExceptionTrace(e)

    trace.render(io)

    expected = """\

Exception

Failed
"""
    assert expected == io.fetch_output()


@pytest.mark.skipif(
    not PY36, reason="Better error messages are only available for Python ^3.6"
)
def test_render_better_error_message():
    io = BufferedIO()

    try:
        raise Exception("Failed")
    except Exception as e:
        trace = ExceptionTrace(e)

    trace.render(io)

    expected = """\

Exception

Failed

at {}:42 in test_render_better_error_message
     38| def test_render_better_error_message():
     39|     io = BufferedIO()
     40| 
     41|     try:
  >  42|         raise Exception("Failed")
     43|     except Exception as e:
     44|         trace = ExceptionTrace(e)
     45| 
     46|     trace.render(io)
""".format(
        __file__
    )
    assert expected == io.fetch_output()


@pytest.mark.skipif(PY36, reason="Legacy error messages are Python <3.6 only")
def test_render_verbose_legacy():
    io = BufferedIO()
    io.set_verbosity(VERBOSE)

    try:
        raise Exception("Failed")
    except Exception as e:
        trace = ExceptionTrace(e)

    trace.render(io)

    msg = "'Failed'"
    if PY38:
        msg = '"Failed"'

    expected = """\

Exception

Failed

Traceback (most recent call last):
  File "{}", line 76, in test_render_verbose_legacy
    raise Exception({})

""".format(
        __file__, msg
    )
    assert expected == io.fetch_output()


@pytest.mark.skipif(
    not PY36, reason="Better error messages are only available for Python ^3.6"
)
def test_render_verbose_better_error_message():
    io = BufferedIO()
    io.set_verbosity(VERBOSE)

    try:
        fail()
    except Exception as e:  # Exception
        trace = ExceptionTrace(e)

    trace.render(io)

    expected = """\

Exception

Failed

at {}:12 in fail
      8| from clikit.utils._compat import PY38
      9| 
     10| 
     11| def fail():
  >  12|     raise Exception("Failed")
     13| 
     14| 
     15| @pytest.mark.skipif(PY36, reason="Legacy error messages are Python <3.6 only")
     16| def test_render_legacy_error_message():

Stack trace:

1 at {}:110 in test_render_verbose_better_error_message
    108| 
    109|     try:
  > 110|         fail()
    111|     except Exception as e:  # Exception
    112|         trace = ExceptionTrace(e)
""".format(
        __file__, __file__
    )
    assert expected == io.fetch_output()
