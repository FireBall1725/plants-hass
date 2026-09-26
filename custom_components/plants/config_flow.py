# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 FireBall1725
"""Add a plant by picking its sensor device."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY,
    CONF_CONDUCTIVITY,
    CONF_DEVICE,
    CONF_ICON,
    CONF_ICON_FILE,
    CONF_ICON_MASK,
    CONF_ILLUMINANCE,
    CONF_MOISTURE,
    CONF_NAME,
    CONF_PROFILE,
    CONF_SPECIES,
    CONF_TEMPERATURE,
    CONF_THRESHOLD,
    DEFAULT_PROFILE,
    DOMAIN,
    ICON_CUSTOM,
    ICONS,
    PROFILE_ICON,
    PROFILES,
    READINGS,
    icon_for,
)
from .icon import IconError, mask_from_file

# Which reading a sensor on the device is, by its device class. Mi Flora reports
# fertility as conductivity.
_DEVICE_CLASS_TO_READING = {
    "moisture": CONF_MOISTURE,
    "temperature": CONF_TEMPERATURE,
    "illuminance": CONF_ILLUMINANCE,
    "conductivity": CONF_CONDUCTIVITY,
    "battery": CONF_BATTERY,
}


def find_sources(hass: HomeAssistant, device_id: str) -> dict[str, str]:
    """The device's sensors, keyed by reading."""
    found: dict[str, str] = {}
    for ent in er.async_entries_for_device(er.async_get(hass), device_id):
        if ent.domain != "sensor" or ent.disabled_by is not None:
            continue
        device_class = ent.device_class or ent.original_device_class
        reading = _DEVICE_CLASS_TO_READING.get(
            str(device_class) if device_class else ""
        )
        if reading and reading not in found:
            found[reading] = ent.entity_id
    return found


def _icon_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[*ICONS, ICON_CUSTOM],
            translation_key="icon",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _file_selector() -> selector.FileSelector:
    return selector.FileSelector(
        selector.FileSelectorConfig(accept="image/png,image/jpeg,image/webp,image/gif")
    )


async def resolve_icon(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    profile: str,
    mask: str | None,
) -> tuple[dict[str, Any], str | None]:
    """The icon options for a submitted form, or an error key.

    An upload picks Custom by itself; Custom without an upload keeps the
    plant's earlier mask, if it has one.
    """
    file_id = user_input.get(CONF_ICON_FILE)
    if file_id:
        try:
            with process_uploaded_file(hass, file_id) as path:
                mask = await hass.async_add_executor_job(mask_from_file, path)
        except IconError as err:
            return {}, str(err)
        return {CONF_ICON: ICON_CUSTOM, CONF_ICON_MASK: mask}, None
    icon = user_input.get(CONF_ICON)
    if icon == ICON_CUSTOM:
        if not mask:
            return {}, "icon_file_required"
        return {CONF_ICON: ICON_CUSTOM, CONF_ICON_MASK: mask}, None
    return {CONF_ICON: icon or PROFILE_ICON[profile]}, None


def _profile_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(PROFILES),
            translation_key="profile",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


class PlantsConfigFlow(ConfigFlow, domain=DOMAIN):
    """One plant per entry."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PlantsOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE]
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()
            sources = find_sources(self.hass, device_id)
            profile = user_input.get(CONF_PROFILE) or DEFAULT_PROFILE
            icon, error = await resolve_icon(self.hass, user_input, profile, None)
            if CONF_MOISTURE not in sources:
                errors["base"] = "no_moisture"
            elif error:
                errors["base"] = error
            else:
                device = dr.async_get(self.hass).async_get(device_id)
                device_name = (device.name_by_user or device.name) if device else None
                name: str = (user_input.get(CONF_NAME) or "").strip() or (
                    device_name or "Plant"
                )
                return self.async_create_entry(
                    title=name,
                    data={CONF_DEVICE: device_id},
                    options={
                        CONF_NAME: name,
                        CONF_SPECIES: (user_input.get(CONF_SPECIES) or "").strip(),
                        CONF_PROFILE: profile,
                        **icon,
                        CONF_THRESHOLD: PROFILES[profile].threshold,
                        **sources,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(
                        entity=[
                            selector.EntityFilterSelectorConfig(
                                domain="sensor", device_class="moisture"
                            )
                        ]
                    )
                ),
                vol.Optional(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_SPECIES): selector.TextSelector(),
                vol.Required(
                    CONF_PROFILE, default=DEFAULT_PROFILE
                ): _profile_selector(),
                vol.Optional(CONF_ICON): _icon_selector(),
                vol.Optional(CONF_ICON_FILE): _file_selector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class PlantsOptionsFlow(OptionsFlow):
    """Rename, re-point a reading, or tune the detector.

    The moisture band lives on the plant's number entities, not here.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        opts = self.config_entry.options
        errors: dict[str, str] = {}
        if user_input is not None:
            profile = user_input.get(CONF_PROFILE) or DEFAULT_PROFILE
            icon, error = await resolve_icon(
                self.hass, user_input, profile, opts.get(CONF_ICON_MASK)
            )
            if error:
                errors["base"] = error
            else:
                data = {
                    k: v
                    for k, v in user_input.items()
                    if v not in (None, "") and k != CONF_ICON_FILE
                }
                data.update(icon)
                data.setdefault(
                    CONF_NAME, opts.get(CONF_NAME) or self.config_entry.title
                )
                return self.async_create_entry(title="", data=data)

        def suggested(key: str) -> dict[str, Any]:
            return {"suggested_value": opts.get(key)}

        fields: dict[Any, Any] = {
            vol.Optional(
                CONF_NAME, description=suggested(CONF_NAME)
            ): selector.TextSelector(),
            vol.Optional(
                CONF_SPECIES, description=suggested(CONF_SPECIES)
            ): selector.TextSelector(),
            vol.Required(
                CONF_PROFILE, default=opts.get(CONF_PROFILE, DEFAULT_PROFILE)
            ): _profile_selector(),
            vol.Required(
                CONF_ICON,
                default=icon_for(
                    opts.get(CONF_ICON),
                    opts.get(CONF_PROFILE),
                    bool(opts.get(CONF_ICON_MASK)),
                ),
            ): _icon_selector(),
            vol.Optional(CONF_ICON_FILE): _file_selector(),
            vol.Required(
                CONF_THRESHOLD,
                default=opts.get(CONF_THRESHOLD, PROFILES[DEFAULT_PROFILE].threshold),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=2,
                    max=40,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="%",
                )
            ),
        }
        for reading in READINGS:
            fields[vol.Optional(reading, description=suggested(reading))] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
            )
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(fields), errors=errors
        )
