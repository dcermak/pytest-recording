from pytest_recording._vcr import load_cassette


def test_no_cassette(testdir):
    """If pytest.mark.vcr is applied and there is no cassette - an exception happens."""
    testdir.makepyfile(
        """
        import pytest
        import requests
        import vcr

        @pytest.mark.vcr
        def test_vcr_used():
            with pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException):
                requests.get('http://localhost/get')
    """
    )

    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_combine_cassettes(testdir, get_response_cassette, ip_response_cassette):
    testdir.makepyfile(
        """
import pytest
import requests

@pytest.mark.vcr("{}")
@pytest.mark.vcr("{}")
def test_combined():
    assert requests.get("http://httpbin.org/get").text == "GET CONTENT"
    assert requests.get("http://httpbin.org/ip").text == "IP CONTENT"

def test_no_vcr(httpbin):
    assert requests.get(httpbin.url + "/headers").status_code == 200
""".format(
            get_response_cassette, ip_response_cassette
        )
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)


def test_combine_cassettes_module_level(testdir, get_response_cassette, ip_response_cassette):
    # When there there is a module-level mark and a test-level mark
    testdir.makepyfile(
        """
import pytest
import requests
import vcr

pytestmark = pytest.mark.vcr("{}")

@pytest.mark.vcr("{}")
def test_combined():
    assert requests.get("http://httpbin.org/get").text == "GET CONTENT"
    assert requests.get("http://httpbin.org/ip").text == "IP CONTENT"

def test_single_cassette():
    assert requests.get("http://httpbin.org/get").text == "GET CONTENT"
    with pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException):
        requests.get("http://httpbin.org/ip")
        """.format(
            get_response_cassette, ip_response_cassette
        )
    )
    # Then their cassettes are combined
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)


def test_empty_module_mark(testdir, get_response_cassette):
    # When a module-level mark is empty
    testdir.makepyfile(
        """
import pytest
import requests
import vcr

pytestmark = pytest.mark.vcr()

@pytest.mark.vcr("{}")
def test_combined():
    assert requests.get("http://httpbin.org/get").text == "GET CONTENT"
""".format(
            get_response_cassette
        )
    )
    # Then it is noop for tests that already have pytest.mark.vcr applied
    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_merged_kwargs(testdir, get_response_cassette):
    # When there are multiple pytest.mark.vcr with different kwargs
    testdir.makepyfile(
        """
import pytest
import requests

def before_request(request):
    raise ValueError("Before")

def override_before_request(request):
    raise ValueError("Overridden")


pytestmark = pytest.mark.vcr(before_record_request=before_request)

GET_CASSETTE = "{}"

@pytest.mark.vcr(GET_CASSETTE)
def test_custom_path():
    with pytest.raises(ValueError, match="Before"):
        requests.get("http://httpbin.org/get")

@pytest.mark.vcr(GET_CASSETTE, before_record_request=override_before_request)
def test_custom_path_with_kwargs():
    with pytest.raises(ValueError, match="Overridden"):
        requests.get("http://httpbin.org/get")
    """.format(
            get_response_cassette
        )
    )
    # Then each test function should have cassettes with merged kwargs
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)


def test_multiple_cassettes_in_mark(testdir, get_response_cassette, ip_response_cassette):
    # When multiple cassettes are specified in pytest.mark.vcr
    testdir.makepyfile(
        """
import pytest
import requests

@pytest.mark.vcr("{}", "{}")
def test_custom_path():
    assert requests.get("http://httpbin.org/get").text == "GET CONTENT"
    assert requests.get("http://httpbin.org/ip").text == "IP CONTENT"
    """.format(
            get_response_cassette, ip_response_cassette
        )
    )
    # Then they should be combined with each other
    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_repeated_cassettes(testdir, mocker, get_response_cassette):
    # When the same cassette is specified multiple times in the same mark or in different ones
    testdir.makepyfile(
        """
import pytest
import requests

CASSETTE = "{}"

pytestmark = [pytest.mark.vcr(CASSETTE)]

@pytest.mark.vcr(CASSETTE, CASSETTE)
def test_custom_path():
    assert requests.get("http://httpbin.org/get").text == "GET CONTENT"
    """.format(
            get_response_cassette
        )
    )
    # Then the cassette will be loaded only once
    # And will not produce any errors
    mocked_load_cassette = mocker.patch("pytest_recording._vcr.load_cassette", wraps=load_cassette)
    result = testdir.runpytest()
    result.assert_outcomes(passed=1)
    assert mocked_load_cassette.call_count == 1


def test_class_mark(testdir, get_response_cassette, ip_response_cassette):
    # When pytest.mark.vcr is applied to a class
    testdir.makepyfile(
        """
import pytest
import requests

pytestmark = [pytest.mark.vcr("{}")]

@pytest.mark.vcr("{}")
class TestSomething:

    @pytest.mark.vcr()
    def test_custom_path(self):
        assert requests.get("http://httpbin.org/get").text == "GET CONTENT"
        assert requests.get("http://httpbin.org/ip").text == "IP CONTENT"
    """.format(
            get_response_cassette, ip_response_cassette
        )
    )
    # Then it should be combined with the other marks
    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_own_mark(testdir, get_response_cassette, create_file, ip_cassette):
    # When a test doesn't have its own mark
    testdir.makepyfile(
        """
import pytest
import requests

pytestmark = [pytest.mark.vcr("{}")]


def test_own():
    assert requests.get("http://httpbin.org/get").text == "GET CONTENT"
    assert requests.get("http://httpbin.org/ip").text == "IP CONTENT"
    """.format(
            get_response_cassette
        )
    )
    create_file("cassettes/test_own_mark/test_own.yaml", ip_cassette)
    # Then it should use a cassette with a default name
    result = testdir.runpytest()
    result.assert_outcomes(passed=1)


def test_name_collision(testdir, create_file, ip_cassette, get_cassette):
    # When different test files contains tests with the same names
    testdir.makepyfile(
        test_a="""
import pytest
import requests

@pytest.mark.vcr
def test_feature():
    assert requests.get("http://httpbin.org/get").text == "GET CONTENT"
    """
    )
    testdir.makepyfile(
        test_b="""
import pytest
import requests

@pytest.mark.vcr
def test_feature():
    assert requests.get("http://httpbin.org/ip").text == "IP CONTENT"
    """
    )
    # Then cassettes should not collide with each other, they should be separate
    create_file("cassettes/test_a/test_feature.yaml", get_cassette)
    create_file("cassettes/test_b/test_feature.yaml", ip_cassette)
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)