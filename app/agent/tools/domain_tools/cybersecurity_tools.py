from __future__ import annotations

import ipaddress
import socket
import time
from typing import Any


class CybersecurityTools:
    """
    Bounded tools for authorized defensive security assessment.

    The scanner performs TCP connection checks only. It does not
    exploit services, authenticate, send protocol payloads, perform
    banner grabbing, or scan unrestricted address/port ranges.
    """

    _MAX_PORTS = 32

    _COMMON_SERVICES = {
        22: "ssh",
        53: "dns",
        80: "http",
        135: "msrpc",
        139: "netbios-ssn",
        443: "https",
        445: "microsoft-ds",
        3389: "rdp",
        5985: "winrm-http",
        5986: "winrm-https",
        8000: "http-alt",
    }

    @staticmethod
    def vulnerability_scan(
        target: str,
        ports: list[int],
        authorization_confirmed: bool,
        timeout: float = 1.0,
    ) -> dict[str, Any]:
        """
        Perform authorized TCP connection checks against one private
        or loopback IP address and a small explicit list of ports.
        """

        normalized_target = (
            CybersecurityTools._validate_target(target)
        )

        normalized_ports = (
            CybersecurityTools._validate_ports(ports)
        )

        if authorization_confirmed is not True:
            raise PermissionError(
                "Explicit target authorization is required."
            )

        if isinstance(timeout, bool) or not isinstance(
            timeout,
            (int, float),
        ):
            raise TypeError(
                "timeout must be a number."
            )

        normalized_timeout = float(timeout)

        if (
            normalized_timeout <= 0
            or normalized_timeout > 10
        ):
            raise ValueError(
                "timeout must be greater than zero "
                "and no more than 10 seconds."
            )

        started = time.perf_counter()
        observations: list[dict[str, Any]] = []

        for port in normalized_ports:
            port_started = time.perf_counter()

            try:
                with socket.create_connection(
                    (normalized_target, port),
                    timeout=normalized_timeout,
                ):
                    state = "open"
                    error = None

            except ConnectionRefusedError:
                state = "closed"
                error = None

            except socket.timeout:
                state = "filtered_or_unresponsive"
                error = "Connection attempt timed out."

            except OSError as exc:
                state = "unreachable_or_filtered"
                error = str(exc)

            observations.append(
                {
                    "port": port,
                    "service_hint":
                        CybersecurityTools
                        ._COMMON_SERVICES.get(
                            port,
                            "unknown",
                        ),
                    "state": state,
                    "duration_seconds": round(
                        time.perf_counter()
                        - port_started,
                        4,
                    ),
                    "error": error,
                }
            )

        open_ports = [
            observation["port"]
            for observation in observations
            if observation["state"] == "open"
        ]

        findings = [
            {
                "finding_id": (
                    f"TCP-{port}-EXPOSED"
                ),
                "severity": "informational",
                "title": (
                    f"TCP port {port} is reachable"
                ),
                "port": port,
                "service_hint":
                    CybersecurityTools
                    ._COMMON_SERVICES.get(
                        port,
                        "unknown",
                    ),
                "interpretation": (
                    "Network reachability was confirmed. "
                    "This does not by itself prove a "
                    "vulnerability."
                ),
                "recommendation": (
                    "Confirm that the service is required, "
                    "patched, authenticated, and restricted "
                    "by host and network firewalls."
                ),
            }
            for port in open_ports
        ]

        return {
            "tool": "Defensive TCP Assessment",
            "domain": "cybersecurity",
            "status": "completed",
            "assessment_type":
                "authorized_tcp_connect_scan",
            "authorization_confirmed": True,
            "target": normalized_target,
            "scope": {
                "target_count": 1,
                "ports_requested": normalized_ports,
                "port_count": len(normalized_ports),
                "maximum_allowed_ports":
                    CybersecurityTools._MAX_PORTS,
                "protocol": "tcp",
            },
            "observations": observations,
            "summary": {
                "open_ports": open_ports,
                "open_count": len(open_ports),
                "other_count": (
                    len(observations)
                    - len(open_ports)
                ),
            },
            "findings": findings,
            "limitations": [
                (
                    "TCP reachability does not establish "
                    "whether a vulnerability exists."
                ),
                (
                    "No exploitation, authentication, "
                    "banner collection, or payload testing "
                    "was performed."
                ),
                (
                    "Service names are port-based hints and "
                    "were not verified from service banners."
                ),
            ],
            "methodology_reference": {
                "standard": "NIST SP 800-115",
                "phase": "discovery",
                "usage":
                    "Authorized, bounded technical assessment",
            },
            "duration_seconds": round(
                time.perf_counter() - started,
                4,
            ),
            "error": None,
        }

    @staticmethod
    def _validate_target(target: str) -> str:
        if not isinstance(target, str):
            raise TypeError(
                "target must be a string containing one IP address."
            )

        normalized_target = target.strip()

        if not normalized_target:
            raise ValueError(
                "target cannot be empty."
            )

        try:
            address = ipaddress.ip_address(
                normalized_target
            )
        except ValueError as exc:
            raise ValueError(
                "target must be one explicit IP address; "
                "hostnames and network ranges are not accepted."
            ) from exc

        if not (
            address.is_private
            or address.is_loopback
        ):
            raise ValueError(
                "Only private or loopback IP addresses "
                "are permitted."
            )

        return str(address)

    @staticmethod
    def _validate_ports(
        ports: list[int],
    ) -> list[int]:
        if not isinstance(ports, list):
            raise TypeError(
                "ports must be an explicit list of integers."
            )

        if not ports:
            raise ValueError(
                "ports cannot be empty."
            )

        if len(ports) > CybersecurityTools._MAX_PORTS:
            raise ValueError(
                "No more than "
                f"{CybersecurityTools._MAX_PORTS} "
                "ports may be checked."
            )

        normalized_ports: list[int] = []

        for port in ports:
            if (
                isinstance(port, bool)
                or not isinstance(port, int)
            ):
                raise TypeError(
                    "Every port must be an integer."
                )

            if port < 1 or port > 65535:
                raise ValueError(
                    "Ports must be between 1 and 65535."
                )

            if port not in normalized_ports:
                normalized_ports.append(port)

        return normalized_ports