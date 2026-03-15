# HA Health Check

[![hacs][hacsbadge]][hacs]
[![License][license-shield]][license]
[![GitHub Release][release-shield]][releases]

A Home Assistant custom integration that exposes a `/healthz` HTTP endpoint for use with Kubernetes liveness and readiness probes.

> **Inspired by [hass-simple-healthcheck](https://github.com/bkupidura/hass-simple-healthcheck) by [@bkupidura](https://github.com/bkupidura).** This project builds on the same concept but is restructured for HACS compatibility and adds a config flow UI, automatic keepalive (no manual automation required), and configurable intervals.

## How It Works

The integration creates a `sensor.ha_health_check_last_seen` sensor entity and runs an internal keepalive timer that periodically updates it with the current timestamp.

The `/healthz` endpoint checks how long ago the last keepalive was received. If the keepalive is within the configured threshold, the endpoint returns healthy. Otherwise, it returns unhealthy.

### What it validates

- Home Assistant HTTP server is responding
- Home Assistant event loop is running (internal keepalive timer fires)
- Sensor entity state can be updated (keepalive updates the sensor)
- Recorder database can persist and retrieve state (when recorder is available)

### What it does NOT validate

Home Assistant is a complex piece of software with many components and integrations. This health check only verifies the aspects listed above.

**It is possible that Home Assistant cannot perform some actions and still be reported as healthy.**

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Tobix99&repository=ha-health-check&category=integration)

1. Open HACS in your Home Assistant instance
2. Click the three dots in the top right corner and select **Custom repositories**
3. Add `https://github.com/Tobix99/ha-health-check` as a custom repository with category **Integration**
4. Search for "HA Health Check" and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/ha_health_check` directory to your Home Assistant `custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "HA Health Check"
4. Configure the options:
   - **Require authentication**: Whether the `/healthz` endpoint requires a long-lived access token (default: `true`)
   - **Unhealthy threshold**: Seconds without a keepalive before reporting unhealthy (default: `60`)
   - **Keepalive interval**: How often the internal keepalive event fires in seconds (default: `10`)

## Kubernetes Configuration

### Without authentication

Set **Require authentication** to `false` in the integration options, then use:

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8123
  initialDelaySeconds: 60
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /healthz
    port: 8123
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### With authentication

Create a [long-lived access token](https://developers.home-assistant.io/docs/auth_api/#long-lived-access-token) in Home Assistant, then use it in the probe:

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8123
    httpHeaders:
      - name: Authorization
        value: "Bearer YOUR_LONG_LIVED_ACCESS_TOKEN"
  initialDelaySeconds: 60
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

## HTTP Endpoint

### Healthy response

```
< HTTP/1.1 200 OK
< Content-Type: application/json

{"healthy": true}
```

### Unhealthy response

```
< HTTP/1.1 503 Service Unavailable
< Content-Type: application/json

{"healthy": false}
```

## Troubleshooting

### Endpoint returns 503
The endpoint returns 503 when the service is unavailable. This can mean the integration is not fully initialized (wait for Home Assistant to finish starting up) or the keepalive threshold has been exceeded.

### Endpoint returns 401
Authentication is enabled (default). Either:
- Set `Require authentication` to `false` in the integration options
- Include a valid long-lived access token in the `Authorization: Bearer <token>` header

### Endpoint always returns unhealthy
- Verify the `threshold` is greater than the `keepalive_interval`
- Check Home Assistant logs for errors from `custom_components.ha_health_check`

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[license]: https://github.com/Tobix99/ha-health-check/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/Tobix99/ha-health-check.svg
[releases]: https://github.com/Tobix99/ha-health-check/releases
[release-shield]: https://img.shields.io/github/release/Tobix99/ha-health-check.svg
