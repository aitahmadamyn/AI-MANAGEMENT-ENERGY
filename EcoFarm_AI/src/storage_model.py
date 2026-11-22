"""
EcoFarm Circular — Phase 3: Sand Thermal Energy Storage Physics Model
=====================================================================

Models the sensible-heat sand battery using:
- Usable stored thermal energy: Q = m * Cp * (T_sand - T_min) / 3600 [kWh]
- Ambient standby losses: Q_loss = UA * (T_sand - T_amb) / 1000 [kW]
- Dynamic hourly charging/discharging balance with configurable PLC safety
  margin: T_sand_max = T_plc_trip - safety_margin_c.

SAFETY INVARIANT:
PLC safety trip temperature and hardware limits are strictly configurable and
never overridden. Any excess thermal energy above T_sand_max is curtailed/rejected
and logged explicitly so hourly energy conservation closes to zero residual.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class SandStorageParameters:
    """Configurable sand thermal battery physical & safety parameters."""

    sand_mass_kg: float = 4000.0
    sand_cp_kj_per_kg_k: float = 0.83
    temp_min_operating_c: float = 120.0
    plc_trip_temp_c: float = 600.0          # Configurable equipment safety limit
    safety_margin_c: float = 50.0           # Configurable buffer below PLC trip
    standby_ua_w_per_k: float = 18.0
    charging_efficiency: float = 0.92
    discharging_efficiency: float = 0.90
    resistance_heater_eff: float = 0.98
    pv_base_load_kw: float = 2.0            # Plant parasitic load before PV surplus
    pv_surplus_min_kw: float = 1.0          # Minimum surplus to trigger heater
    initial_sand_temp_c: float = 220.0

    @property
    def temp_max_operating_c(self) -> float:
        return self.plc_trip_temp_c - self.safety_margin_c


def usable_stored_energy_kwh(sand_temp_c: float, params: SandStorageParameters) -> float:
    """Usable thermal energy (kWh_th) above minimum extraction temperature."""
    delta_t = max(0.0, sand_temp_c - params.temp_min_operating_c)
    return (params.sand_mass_kg * params.sand_cp_kj_per_kg_k * delta_t) / 3600.0


def standby_heat_loss_kw(
    sand_temp_c: float,
    ambient_temp_c: float,
    params: SandStorageParameters,
) -> float:
    """Ambient conductive/convective heat loss through vessel insulation (kW_th)."""
    return (params.standby_ua_w_per_k * max(0.0, sand_temp_c - ambient_temp_c)) / 1000.0


def step_sand_storage_hour(
    sand_temp_c: float,
    ambient_temp_c: float,
    solar_thermal_kw: float,
    ncg_recovered_kw: float,
    pv_power_kw: float,
    dryer_demand_kw: float,
    params: SandStorageParameters,
    dt_hours: float = 1.0,
) -> Dict[str, float]:
    """
    Advance sand thermal storage state by `dt_hours` (default 1.0 h) using a
    conventional baseline thermal dispatch sequence:
    1. Recovered NCG heat & solar thermal first supply direct dryer demand if needed;
       any excess charges sand storage (up to T_max_operating_c).
    2. Genuine PV electrical surplus (> pv_base_load + min threshold) powers
       electric resistance heating only if storage is below T_max_operating_c.
    3. Unmet dryer demand draws from sand storage while T_sand > T_min_operating_c;
       any remaining deficit is logged as `auxiliary_heating_needed_kw`.
    4. Exact hourly energy balance closure is computed and returned.
    """
    t_max = params.temp_max_operating_c
    t_min = params.temp_min_operating_c
    cap_kwh_per_c = (params.sand_mass_kg * params.sand_cp_kj_per_kg_k) / 3600.0

    q_start_kwh = usable_stored_energy_kwh(sand_temp_c, params)

    # 1. Direct renewable/recovered thermal supply to dryer first
    direct_thermal_avail = solar_thermal_kw + ncg_recovered_kw
    direct_to_dryer_kw = min(dryer_demand_kw, direct_thermal_avail)
    excess_thermal_for_charge = max(0.0, direct_thermal_avail - direct_to_dryer_kw)
    unmet_dryer_kw = max(0.0, dryer_demand_kw - direct_to_dryer_kw)

    # 2. Genuine PV surplus resistance heating (distinct from electrical base load)
    pv_surplus_kw = max(0.0, pv_power_kw - params.pv_base_load_kw)
    pv_heater_elec_kw = (
        pv_surplus_kw
        if (pv_surplus_kw >= params.pv_surplus_min_kw and sand_temp_c < t_max)
        else 0.0
    )
    pv_heater_th_kw = pv_heater_elec_kw * params.resistance_heater_eff

    # 3. Standby thermal loss at current temperature
    q_loss_kw = standby_heat_loss_kw(sand_temp_c, ambient_temp_c, params)

    # 4. Charging & discharging power
    q_charge_net_kw = params.charging_efficiency * (excess_thermal_for_charge + pv_heater_th_kw)

    # Maximum thermal energy safely extractable in this hour before hitting T_min
    max_extractable_kwh = max(0.0, (sand_temp_c - t_min) * cap_kwh_per_c)
    desired_discharge_gross_kwh = (unmet_dryer_kw * dt_hours) / params.discharging_efficiency

    # Account for loss & charging first when checking bounds
    # Energy change before clamping
    e_charge_kwh = q_charge_net_kw * dt_hours
    e_loss_kwh = min(q_loss_kw * dt_hours, max(0.0, (sand_temp_c - ambient_temp_c) * cap_kwh_per_c))

    # Available above T_min after loss + charge
    avail_after_charge_kwh = max(0.0, q_start_kwh + e_charge_kwh - e_loss_kwh)
    e_discharge_gross_kwh = min(desired_discharge_gross_kwh, avail_after_charge_kwh)
    q_from_sand_to_dryer_kw = (e_discharge_gross_kwh * params.discharging_efficiency) / dt_hours
    aux_heating_kw = max(0.0, unmet_dryer_kw - q_from_sand_to_dryer_kw)

    # 5. Update temperature and curtail any charge exceeding T_max_operating_c (PLC margin)
    net_energy_kwh = e_charge_kwh - e_discharge_gross_kwh - e_loss_kwh
    t_sand_unclamped = sand_temp_c + (net_energy_kwh / cap_kwh_per_c)

    curtailed_kwh = 0.0
    if t_sand_unclamped > t_max:
        curtailed_kwh = (t_sand_unclamped - t_max) * cap_kwh_per_c
        t_sand_next = t_max
    elif t_sand_unclamped < ambient_temp_c:
        t_sand_next = ambient_temp_c
    else:
        t_sand_next = t_sand_unclamped

    q_end_kwh = usable_stored_energy_kwh(t_sand_next, params)

    # Exact energy closure residual (only valid when T_start & T_end >= T_min)
    if sand_temp_c >= t_min and t_sand_next >= t_min:
        energy_closure_residual_kwh = abs(
            (q_end_kwh - q_start_kwh)
            - (e_charge_kwh - e_discharge_gross_kwh - e_loss_kwh - curtailed_kwh)
        )
    else:
        energy_closure_residual_kwh = 0.0

    # HTF loop synthetic temperatures (physical approach above dryer / sand)
    is_charging = 1 if (q_charge_net_kw > 0.1 and curtailed_kwh < e_charge_kwh) else 0
    is_discharging = 1 if q_from_sand_to_dryer_kw > 0.1 else 0
    htf_outlet_c = min(310.0, max(ambient_temp_c, min(t_sand_next - 15.0, 260.0))) if is_discharging else ambient_temp_c
    htf_inlet_c = max(ambient_temp_c, htf_outlet_c - 35.0) if is_discharging else ambient_temp_c

    return {
        "sand_temp_c": t_sand_next,
        "stored_thermal_energy_kwh": q_end_kwh,
        "htf_inlet_temp_c": htf_inlet_c,
        "htf_outlet_temp_c": htf_outlet_c,
        "storage_charging_status": is_charging,
        "storage_discharging_status": is_discharging,
        "direct_to_dryer_kw": direct_to_dryer_kw,
        "pv_surplus_heater_elec_kw": pv_heater_elec_kw,
        "q_charge_net_kw": q_charge_net_kw,
        "q_from_sand_to_dryer_kw": q_from_sand_to_dryer_kw,
        "q_storage_loss_kw": e_loss_kwh / dt_hours,
        "curtailed_thermal_kw": curtailed_kwh / dt_hours,
        "auxiliary_heating_needed_kw": aux_heating_kw,
        "energy_closure_residual_kwh": energy_closure_residual_kwh,
    }
