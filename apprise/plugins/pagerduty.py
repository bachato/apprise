# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# API Refererence:
#   - https://developer.pagerduty.com/api-reference/\
#       368ae3d938c9e-send-an-event-to-pager-duty
#

from json import dumps

import requests

from ..common import NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_bool, validate_regex
from .base import NotifyBase


class PagerDutySeverity:
    """Defines the Pager Duty Severity Levels."""

    INFO = "info"

    WARNING = "warning"

    ERROR = "error"

    CRITICAL = "critical"


# Map all support Apprise Categories with the Pager Duty ones
PAGERDUTY_SEVERITY_MAP = {
    NotifyType.INFO: PagerDutySeverity.INFO,
    NotifyType.SUCCESS: PagerDutySeverity.INFO,
    NotifyType.WARNING: PagerDutySeverity.WARNING,
    NotifyType.FAILURE: PagerDutySeverity.CRITICAL,
}

PAGERDUTY_SEVERITIES = (
    PagerDutySeverity.INFO,
    PagerDutySeverity.WARNING,
    PagerDutySeverity.CRITICAL,
    PagerDutySeverity.ERROR,
)


# Priorities
class PagerDutyRegion:
    US = "us"
    EU = "eu"


# SparkPost APIs
PAGERDUTY_API_LOOKUP = {
    PagerDutyRegion.US: "https://events.pagerduty.com/v2/enqueue",
    PagerDutyRegion.EU: "https://events.eu.pagerduty.com/v2/enqueue",
}

# A List of our regions we can use for verification
PAGERDUTY_REGIONS = (
    PagerDutyRegion.US,
    PagerDutyRegion.EU,
)


class NotifyPagerDuty(NotifyBase):
    """A wrapper for Pager Duty Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Pager Duty"

    # The services URL
    service_url = "https://pagerduty.com/"

    # Secure Protocol
    secure_protocol = "pagerduty"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_pagerduty"

    # We don't support titles for Pager Duty notifications
    title_maxlen = 0

    # Allows the user to specify the NotifyImageSize object; this is supported
    # through the webhook
    image_size = NotifyImageSize.XY_128

    # Our event action type
    event_action = "trigger"

    # The default region to use if one isn't otherwise specified
    default_region = PagerDutyRegion.US

    # Define object templates
    templates = (
        "{schema}://{integrationkey}@{apikey}",
        "{schema}://{integrationkey}@{apikey}/{source}",
        "{schema}://{integrationkey}@{apikey}/{source}/{component}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            # Optional but triggers V2 API
            "integrationkey": {
                "name": _("Integration Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "source": {
                # Optional Source Identifier (preferably a FQDN)
                "name": _("Source"),
                "type": "string",
                "default": "Apprise",
            },
            "component": {
                # Optional Component Identifier
                "name": _("Component"),
                "type": "string",
                "default": "Notification",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "group": {
                "name": _("Group"),
                "type": "string",
            },
            "class": {
                "name": _("Class"),
                "type": "string",
                "map_to": "class_id",
            },
            "click": {
                "name": _("Click"),
                "type": "string",
            },
            "region": {
                "name": _("Region Name"),
                "type": "choice:string",
                "values": PAGERDUTY_REGIONS,
                "default": PagerDutyRegion.US,
                "map_to": "region_name",
            },
            # The severity is automatically determined, however you can
            # optionally over-ride its value and force it to be what you want
            "severity": {
                "name": _("Severity"),
                "type": "choice:string",
                "values": PAGERDUTY_SEVERITIES,
                "map_to": "severity",
            },
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "details": {
            "name": _("Custom Details"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        apikey,
        integrationkey=None,
        source=None,
        component=None,
        group=None,
        class_id=None,
        include_image=True,
        click=None,
        details=None,
        region_name=None,
        severity=None,
        **kwargs,
    ):
        """Initialize Pager Duty Object."""
        super().__init__(**kwargs)

        # Long-Lived Access token (generated from User Profile)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid Pager Duty API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.integration_key = validate_regex(integrationkey)
        if not self.integration_key:
            msg = (
                "An invalid Pager Duty Routing Key "
                f"({integrationkey}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # An Optional Source
        self.source = self.template_tokens["source"]["default"]
        if source:
            self.source = validate_regex(source)
            if not self.source:
                msg = (
                    "An invalid Pager Duty Notification Source "
                    f"({source}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.component = self.template_tokens["source"]["default"]

        # An Optional Component
        self.component = self.template_tokens["component"]["default"]
        if component:
            self.component = validate_regex(component)
            if not self.component:
                msg = (
                    "An invalid Pager Duty Notification Component "
                    f"({component}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.component = self.template_tokens["component"]["default"]

        # Store our region
        try:
            self.region_name = (
                self.default_region
                if region_name is None
                else region_name.lower()
            )

            if self.region_name not in PAGERDUTY_REGIONS:
                # allow the outer except to handle this common response
                raise IndexError()

        except (AttributeError, IndexError, TypeError):
            # Invalid region specified
            msg = f"The PagerDuty region specified ({region_name}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg) from None

        # The severity (if specified)
        self.severity = (
            None
            if severity is None
            else next(
                (
                    s
                    for s in PAGERDUTY_SEVERITIES
                    if str(s).lower().startswith(severity)
                ),
                False,
            )
        )

        if self.severity is False:
            # Invalid severity specified
            msg = f"The PagerDuty severity specified ({severity}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        # A clickthrough option for notifications
        self.click = click

        # Store Class ID if specified
        self.class_id = class_id

        # Store Group if specified
        self.group = group

        self.details = {}
        if details:
            # Store our extra details
            self.details.update(details)

        # Display our Apprise Image
        self.include_image = include_image

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Send our PagerDuty Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": f"Token token={self.apikey}",
        }

        # Prepare our persistent_notification.create payload
        payload = {
            # Define our integration key
            "routing_key": self.integration_key,
            # Prepare our payload
            "payload": {
                "summary": body,
                # Set our severity
                "severity": (
                    PAGERDUTY_SEVERITY_MAP[notify_type]
                    if not self.severity
                    else self.severity
                ),
                # Our Alerting Source/Component
                "source": self.source,
                "component": self.component,
            },
            "client": self.app_id,
            # Our Event Action
            "event_action": self.event_action,
        }

        if self.group:
            payload["payload"]["group"] = self.group

        if self.class_id:
            payload["payload"]["class"] = self.class_id

        if self.click:
            payload["links"] = [{
                "href": self.click,
            }]

        # Acquire our image url if configured to do so
        image_url = (
            None if not self.include_image else self.image_url(notify_type)
        )

        if image_url:
            payload["images"] = [{
                "src": image_url,
                "alt": notify_type,
            }]

        if self.details:
            payload["payload"]["custom_details"] = {}
            # Apply any provided custom details
            for k, v in self.details.items():
                payload["payload"]["custom_details"][k] = v

        # Prepare our URL based on region
        notify_url = PAGERDUTY_API_LOOKUP[self.region_name]

        self.logger.debug(
            "Pager Duty POST URL:"
            f" {notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Pager Duty Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code not in (
                requests.codes.ok,
                requests.codes.created,
                requests.codes.accepted,
            ):
                # We had a problem
                status_str = NotifyPagerDuty.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Pager Duty notification: "
                    "{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Return; we're done
                return False

            else:
                self.logger.info("Sent Pager Duty notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Pager Duty "
                f"notification to {self.host}."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Return; we're done
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.integration_key,
            self.apikey,
            self.source,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "region": self.region_name,
            "image": "yes" if self.include_image else "no",
        }
        if self.class_id:
            params["class"] = self.class_id

        if self.group:
            params["group"] = self.group

        if self.click is not None:
            params["click"] = self.click

        if self.severity:
            params["severity"] = self.severity

        # Append our custom entries our parameters
        params.update({f"+{k}": v for k, v in self.details.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        url = (
            "{schema}://{integration_key}@{apikey}/"
            "{source}/{component}?{params}"
        )

        return url.format(
            schema=self.secure_protocol,
            # never encode hostname since we're expecting it to be a valid one
            integration_key=self.pprint(
                self.integration_key, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            apikey=self.pprint(
                self.apikey, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            source=self.pprint(self.source, privacy, safe=""),
            component=self.pprint(self.component, privacy, safe=""),
            params=NotifyPagerDuty.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The 'apikey' makes it easier to use yaml configuration
        if "apikey" in results["qsd"] and len(results["qsd"]["apikey"]):
            results["apikey"] = NotifyPagerDuty.unquote(
                results["qsd"]["apikey"]
            )
        else:
            results["apikey"] = NotifyPagerDuty.unquote(results["host"])

        # The 'integrationkey' makes it easier to use yaml configuration
        if "integrationkey" in results["qsd"] and len(
            results["qsd"]["integrationkey"]
        ):
            results["integrationkey"] = NotifyPagerDuty.unquote(
                results["qsd"]["integrationkey"]
            )
        else:
            results["integrationkey"] = NotifyPagerDuty.unquote(
                results["user"]
            )

        if "click" in results["qsd"] and len(results["qsd"]["click"]):
            results["click"] = NotifyPagerDuty.unquote(results["qsd"]["click"])

        if "group" in results["qsd"] and len(results["qsd"]["group"]):
            results["group"] = NotifyPagerDuty.unquote(results["qsd"]["group"])

        if "class" in results["qsd"] and len(results["qsd"]["class"]):
            results["class_id"] = NotifyPagerDuty.unquote(
                results["qsd"]["class"]
            )

        if "severity" in results["qsd"] and len(results["qsd"]["severity"]):
            results["severity"] = NotifyPagerDuty.unquote(
                results["qsd"]["severity"]
            )

        # Acquire our full path
        fullpath = NotifyPagerDuty.split_path(results["fullpath"])

        # Get our source
        if "source" in results["qsd"] and len(results["qsd"]["source"]):
            results["source"] = NotifyPagerDuty.unquote(
                results["qsd"]["source"]
            )
        else:
            results["source"] = fullpath.pop(0) if fullpath else None

        # Get our component
        if "component" in results["qsd"] and len(results["qsd"]["component"]):
            results["component"] = NotifyPagerDuty.unquote(
                results["qsd"]["component"]
            )
        else:
            results["component"] = fullpath.pop(0) if fullpath else None

        # Add our custom details key/value pairs that the user can potentially
        # over-ride if they wish to to our returned result set and tidy
        # entries by unquoting them
        results["details"] = {
            NotifyPagerDuty.unquote(x): NotifyPagerDuty.unquote(y)
            for x, y in results["qsd+"].items()
        }

        if "region" in results["qsd"] and len(results["qsd"]["region"]):
            # Extract from name to associate with from address
            results["region_name"] = NotifyPagerDuty.unquote(
                results["qsd"]["region"]
            )

        # Include images with our message
        results["include_image"] = parse_bool(
            results["qsd"].get("image", True)
        )

        return results
