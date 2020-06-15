from typing import Union
import json
import logging
import re
import warnings
import requests
import pkg_resources
from bs4 import BeautifulSoup

logger = logging.getLogger(name=__name__)

class WebContent:
    """
    Store web page information using requests package.
    """

    def __init__(self, url, verify: bool = True, timeout: Union[int, float] = 2.5):
        """
        Initialize a new WebContent object.

        Parameters
        ----------

        url : str
            The web page URL.
        verify : bool
            SSL check (default=True).
        timeout : Union[int, float]
            Stop waiting for a repsonse after timeout (seconds) if no response has been received yet.
        """
        self.url = url

        response = requests.get(url, verify=verify, timeout=timeout)
        self.html = response.text
        self.headers = response.headers
        self.cookies = response.cookies.get_dict()

        html_parsed = BeautifulSoup(self.html, "lxml")
        self.scripts = [script['src'] for script in
                        html_parsed.findAll('script', src=True)]
        self.meta_data = {
            meta['name'].lower():
                meta['content'] for meta in html_parsed.findAll(
                    'meta', attrs=dict(name=True, content=True))
        }
        self.icons = [icon['src'] for icon in html_parsed.findAll(['img', 'svg', 'i'], src=True)]
        self.icons.append([icon['href'] for icon in html_parsed.findAll('link', rel="icon", href=True)])

    def get_url(self):
        """Provide the WebContent url"""
        return self.url

    def get_html(self):
        """Provide the html response of the request done on the WebContent url"""
        return self.html

    def get_headers(self):
        """Provide the response headers of the request done on the WebContent url"""
        return self.headers

    def get_cookies(self):
        """Provide the response cookies of the request done on the WebContent url"""
        return self.cookies

    def get_scripts(self):
        """Provide the scripts extracted from the html reponse of the request done on the WebContent url"""
        return self.scripts

    def get_meta_data(self):
        """Provide the meta data extracted from the html reponse of the request done on the WebContent url"""
        return self.meta_data

    def get_icons(self):
        """Provide the images extracted from the html reponse of the request done on the WebContent url"""
        return self.icons

class ApplicationDataException(Exception):
    """Raised when application data file is not properly formatted"""
    def __init__(self, message):
        message = "Application data file is not properly formatted : " + message
        super().__init__(message)

class ApplicationData:
    """
    Store application database.
    For instance https://raw.githubusercontent.com/AliasIO/wappalyzer/master/src/apps.json.
    """
    def __init__(self, data_filename=None):
        """
        Initialize a new ApplicationData object.

        Parameters
        ----------

        data_filename : str
            File providing application and categorie references (Json format).
        """
        if data_filename:
            with open(data_filename, 'r') as data_file:
                obj = json.load(data_file)
        else:
            obj = json.loads(pkg_resources.resource_string(__name__, "data/apps.json"))

        self.applications = obj["apps"]
        self.normalize_applications()
        self.normalize_application_regex()
        self.categories = obj["categories"]
        self.normalize_categories()

    def normalize_applications(self):
        """
        Ensure that each needed field is at least an empty element
        """
        for application_name in self.applications:

            for list_field in ["cats", "html", "implies", "script"]:
                if list_field not in self.applications[application_name]:
                    # Complete with empty elements if not already present
                    self.applications[application_name][list_field] = []
                elif not isinstance(self.applications[application_name][list_field], list):
                    # Ensure to not iterate on a string value
                    self.applications[application_name][list_field] = [self.applications[application_name][list_field]]

            for dict_field in ["meta", "js", "cookies", "headers"]:
                if dict_field not in self.applications[application_name]:
                    # Complete with empty elements if not already present
                    self.applications[application_name][dict_field] = {}
                elif not isinstance(self.applications[application_name][dict_field], dict):
                    # Raise an exception if the provided field is not a dict
                    raise ApplicationDataException("{0} is not a dict in {1}".format(
                        dict_field,
                        self.applications[application_name]))

                # Ensure keys are lowercase
                dict_items = self.applications[application_name][dict_field].items()
                self.applications[application_name][dict_field] = {key.lower():value for (key, value) in dict_items}

            for string_field in ["url", "icon", "website", "cpe"]:
                if string_field not in self.applications[application_name]:
                    # Complete with empty elements if not already present
                    self.applications[application_name][string_field] = ""
                elif not isinstance(self.applications[application_name][string_field], str):
                    # Ensure to not evaluate a list or dict
                    self.applications[application_name][string_field] = str(
                        self.applications[application_name][string_field])

    def normalize_categories(self):
        """
        Ensure that at least each needed field exists
        """
        for category in self.categories:
            for field in ["name"]:
                if field not in self.categories[category]:
                    raise ApplicationDataException("{0} field is not in {1}".format(field, self.categories[category]))

    def normalize_application_regex(self):
        """
        Format application regex provided in interesting fields
        """
        for application_name in self.applications:

            for list_field in ["html", "implies", "script"]:
                self.applications[application_name][list_field] = [
                    self.normalize_regex(pattern) for pattern in self.applications[application_name][list_field]
                    ]

            for dict_field in ["meta", "cookies", "headers"]:
                for (key, pattern) in self.applications[application_name][dict_field].items():
                    # Sometimes key is provided but pattern is empty
                    # However looking for key seems to be interesting
                    if pattern == "":
                        pattern = key
                    self.applications[application_name][dict_field][key] = self.normalize_regex(pattern)

            for string_field in ["url"]:
                regex = self.applications[application_name][string_field]
                if regex != '':
                    self.applications[application_name][string_field] = self.normalize_regex(regex)

    def normalize_regex(self, pattern: str):
        """
        Return a dict containing version regex and application regex extracted from pattern string and compiled regex
        """
        regex_params = {}
        pattern = pattern.split("\\;")
        for i, expression in enumerate(pattern):
            if i == 0:
                regex_params["application_pattern"] = expression
                try:
                    regex_params['regex'] = re.compile(expression, re.I)
                except re.error as err:
                    warnings.warn(
                        "Caught {0} while compiling regex: {1}".format(err, pattern)
                    )
                    # regex that never matches:
                    # http://stackoverflow.com/a/1845097/413622
                    regex_params['regex'] = re.compile(r'(?!x)x')
            else:
                splitted_param_pattern = expression.split(':')
                if len(splitted_param_pattern) > 1:
                    param = splitted_param_pattern.pop(0)
                    regex_params[param] = ':'.join(splitted_param_pattern)
        return regex_params

    def get_categories(self):
        """Provide normalized ApplicationData categories"""
        return self.categories

    def get_applications(self):
        """Provide normalized ApplicationData applications"""
        return self.applications

class Wappalyzer:
    """
    Python Wappalyzer driver.
    """

    def __init__(self, application_data: ApplicationData, web_content: WebContent):
        """
        Initialize a new Wappalyzer object.
        """
        self.applications = application_data.get_applications()
        self.categories = application_data.get_categories()
        self.web_content = web_content

    def is_application_detected(self, application: dict):
        """
        Determine whether the web content matches the application regex.
        """
        web_content = self.web_content
        web_url = web_content.get_url()
        web_headers = web_content.get_headers()
        web_scripts = web_content.get_scripts()
        web_cookies = web_content.get_cookies()
        web_meta_data = web_content.get_meta_data()
        web_html = web_content.get_html()

        is_detected = (
            self.is_application_detected_normalize_string(application, 'url', web_url) or
            self.is_application_detected_normalize_list(application, 'html', web_html) or
            self.is_application_detected_normalize_list(application, 'script', web_scripts) or
            self.is_application_detected_normalize_dict(application, 'cookies', web_cookies) or
            self.is_application_detected_normalize_dict(application, 'headers', web_headers) or
            self.is_application_detected_normalize_dict(application, 'meta', web_meta_data)
            )

        return is_detected

    def is_application_detected_normalize_string(self, application: dict, content_type: str, contents):
        """
        Determine whether the content matches the application regex
        Add a new version of application if the content matches
        """
        is_detected = False
        if application[content_type] != '':
            if re.search(application[content_type]['regex'], contents):
                is_detected = True
                self.update_version_detected(application, application[content_type], contents)

        return is_detected

    def is_application_detected_normalize_list(self, application: dict, content_type: str, contents):
        """
        Determine whether the content matches the application regex
        Add a new version of application if the content matches
        """
        is_detected = False

        for regex_params in application[content_type]:
            for content in contents:
                if re.search(regex_params['regex'], content):
                    is_detected = True
                    self.update_version_detected(application, regex_params, content)

        return is_detected

    def is_application_detected_normalize_dict(self, application: dict, content_type: str, contents):
        """
        Determine whether the content matches the application regex
        Add a new version of application if the content matches
        """
        is_detected = False
        for (key, regex_params) in application[content_type].items():
            if key in contents:
                if re.search(regex_params['regex'], contents[key]):
                    is_detected = True
                    self.update_version_detected(application, regex_params, contents[key])

        return is_detected

    def update_version_detected(self, application: dict, regex_params, content):
        """
        Add a new detected version of application.
        """
        if 'version' in regex_params:
            found_occurrences = re.findall(regex_params['regex'], content)
            for occurrence in found_occurrences:
                version_pattern = regex_params['version']

                # Ensure to not iterate on a string value
                if isinstance(occurrence, str):
                    occurrence = [occurrence]
                for i, match in enumerate(occurrence):
                    # Parse ternary operator : version:\\1?\\1:\\2
                    ternary = re.search(re.compile('\\\\' + str(i + 1) + '\\?([^:]+):(.*)$', re.I), version_pattern)
                    if (ternary and len(ternary.groups()) == 2
                            and ternary.group(1) is not None
                            and ternary.group(2) is not None):
                        version_pattern = version_pattern.replace(ternary.group(0), ternary.group(1) if match != ''
                                                                  else ternary.group(2))

                    # Replace back references
                    version_pattern = version_pattern.replace('\\' + str(i + 1), match)
                if version_pattern != '':
                    if 'versions' not in application:
                        application['versions'] = [version_pattern]
                    elif version_pattern not in application['versions']:
                        application['versions'].append(version_pattern)

    def get_rec_implied_applications(self, detected_applications: set):
        """
        Return the set of applications implied by the already detected applications.
        """

        init_implied_applications = self.get_implied_applications(detected_applications)
        final_implied_applications = set()

        while not final_implied_applications.issuperset(init_implied_applications):
            final_implied_applications.update(init_implied_applications)
            init_implied_applications = self.get_implied_applications(final_implied_applications)

        return final_implied_applications

    def get_implied_applications(self, applications: set):
        """Look for implied applications"""
        final_implied_applications = set()

        for application_name in applications:
            implied_applications = self.applications[application_name]['implies']

            for regex_params in implied_applications:
                final_implied_applications.update(set([regex_params['application_pattern']]))
        return final_implied_applications

    def get_categories(self, application_name: str):
        """
        Returns a list of the categories for a name of application.
        """
        category_numbers = self.applications.get(application_name, {}).get("cats", [])
        category_names = [self.categories.get(str(category_number), "").get("name", "")
                          for category_number in category_numbers]

        return category_names

    def get_versions(self, application_name: str):
        """
        Retuns a list of the discovered versions for a name of application.
        """
        return ([] if 'versions' not in self.applications[application_name]
                else self.applications[application_name]['versions'])

    def detect(self):
        """
        Return a list of applications that can be detected on web content.
        """
        detected_applications = set()
        applications = self.applications
        # Try to detect some applications
        for application_name in applications:
            if self.is_application_detected(applications[application_name]):
                detected_applications.add(application_name)

        # Add implied applications
        detected_applications |= self.get_rec_implied_applications(detected_applications)

        return detected_applications

    def detect_with_versions(self):
        """
        Return a list of applications with the versions that can be detected on the web page.
        """
        detected_applications = self.detect()
        versioned_applications = {}

        for application_name in detected_applications:
            versions = self.get_versions(application_name)
            versioned_applications[application_name] = {"versions": versions}

        return versioned_applications

    def detect_with_versions_and_categories(self):
        """
        Return a list of applications with their categories and the versions that can be detected on web content.
        """
        versioned_applications = self.detect_with_versions()
        versioned_and_categorised_applications = versioned_applications

        for application_name in versioned_applications:
            category_names = self.get_categories(application_name)
            versioned_and_categorised_applications[application_name]["categories"] = category_names

        return versioned_and_categorised_applications