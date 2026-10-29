import math
import calendar
from copy import deepcopy
inputs = {'system_type': 'on-grid', 'year': 2025, 'monthly_consumption_kwh': 600, 'monthly_psh': [4, 4.5, 5, 5.5, 6, 6.5, 6.5, 6, 5.5, 5, 4.5, 4], 'solar_source': 'Illustrative solar resource; NOT measured Alice Springs or NASA data', 'solar_period': 'Editable teaching scenario; replace with verified monthly site resource', 'usable_roof_m2': 40, 'panel_watt': 550, 'panel_length_m': 2.28, 'panel_width_m': 1.13, 'performance_ratio': 0.8, 'target_offset': 1.0, 'spacing_factor': 1.2, 'design_dc_ac_ratio': 1.1, 'panel_price_aud': 250, 'bos_cost_aud': 1500, 'annual_maintenance_aud': 150, 'import_tariff_aud': 0.30, 'export_enabled': False, 'export_tariff_aud': 0.05, 'self_consumption_ratios': [0.4, 0.6, 0.8], 'prices_note': 'Illustrative AUD inputs only; replace with Australian supplier quotes and your tariff. Not an exchange-rate conversion.', 'inverter_catalog': [{'name': 'Demo-3', 'rated_ac_kw': 3, 'price_aud': 1200}, {'name': 'Demo-5', 'rated_ac_kw': 5, 'price_aud': 1800}, {'name': 'Demo-8', 'rated_ac_kw': 8, 'price_aud': 2500}]}

def check_number(value, name, minimum=0, maximum=None, allow_minimum=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be numeric')
    if not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    if value < minimum or (value == minimum and (not allow_minimum)):
        raise ValueError(f'{name} is too small')
    if maximum is not None and value > maximum:
        raise ValueError(f'{name} is too large')

def validate(data):
    expected = set(inputs)
    if set(data) != expected:
        raise ValueError("Input fields do not match this notebook's schema")
    if data['system_type'] != 'on-grid':
        raise ValueError('This notebook supports on-grid without batteries only')
    if not isinstance(data['export_enabled'], bool):
        raise ValueError('export_enabled must be a boolean')
    year = data['year']
    if isinstance(year, bool) or not isinstance(year, int) or (not 1900 <= year <= 9999):
        raise ValueError('Invalid calendar year')
    for name in ('solar_source', 'solar_period', 'prices_note'):
        if not isinstance(data[name], str) or not data[name].strip():
            raise ValueError(f'{name} is required')
    for name in ('monthly_consumption_kwh', 'usable_roof_m2', 'panel_watt', 'panel_length_m', 'panel_width_m', 'design_dc_ac_ratio'):
        check_number(data[name], name)
    for name in ('panel_price_aud', 'bos_cost_aud', 'annual_maintenance_aud', 'import_tariff_aud', 'export_tariff_aud'):
        check_number(data[name], name, allow_minimum=True)
    for name in ('performance_ratio', 'target_offset'):
        check_number(data[name], name, maximum=1)
    check_number(data['spacing_factor'], 'spacing_factor', minimum=1, allow_minimum=True)
    if not isinstance(data['monthly_psh'], (list, tuple)) or len(data['monthly_psh']) != 12:
        raise ValueError('Exactly 12 monthly PSH values are required')
    for value in data['monthly_psh']:
        check_number(value, 'monthly_psh')
    ratios = data['self_consumption_ratios']
    if not isinstance(ratios, (list, tuple)) or not ratios:
        raise ValueError('At least one scenario is required')
    for value in ratios:
        check_number(value, 'self_consumption_ratio', maximum=1, allow_minimum=True)
    if not isinstance(data['inverter_catalog'], list):
        raise ValueError('inverter_catalog must be a list')
    for item in data['inverter_catalog']:
        if not isinstance(item, dict) or set(item) != {'name', 'rated_ac_kw', 'price_aud'}:
            raise ValueError('Invalid inverter catalog entry')
        if not isinstance(item['name'], str) or not item['name'].strip():
            raise ValueError('Inverter name is required')
        check_number(item['rated_ac_kw'], 'rated_ac_kw')
        check_number(item['price_aud'], 'price_aud', allow_minimum=True)

def prepare_solar(data):
    days = [calendar.monthrange(data['year'], month)[1] for month in range(1, 13)]
    sun_hours = [psh * count for psh, count in zip(data['monthly_psh'], days)]
    return {'days_per_month': days, 'annual_mean_psh': sum(sun_hours) / sum(days), 'annual_yield_per_kwp': sum(sun_hours) * data['performance_ratio'], 'source': data['solar_source'], 'period': data['solar_period']}

def choose_panels(data, solar):
    annual_demand = data['monthly_consumption_kwh'] * 12
    required_kwp = annual_demand * data['target_offset'] / solar['annual_yield_per_kwp']
    requested_count = math.ceil(required_kwp * 1000 / data['panel_watt'])
    area_per_panel = data['panel_length_m'] * data['panel_width_m'] * data['spacing_factor']
    roof_limit = math.floor(data['usable_roof_m2'] / area_per_panel)
    selected_count = min(requested_count, roof_limit)
    return {'required_kwp': required_kwp, 'requested_count': requested_count, 'requested_area_m2': requested_count * area_per_panel, 'selected_count': selected_count, 'installed_kwp': selected_count * data['panel_watt'] / 1000, 'selected_area_m2': selected_count * area_per_panel, 'roof_limited': selected_count < requested_count}

def choose_inverter(data, panels):
    if panels['selected_count'] == 0:
        return None
    target_ac_kw = panels['installed_kwp'] / data['design_dc_ac_ratio']
    candidates = [item for item in data['inverter_catalog'] if item['rated_ac_kw'] >= target_ac_kw]
    if not candidates:
        return None
    selected = min(candidates, key=lambda item: item['rated_ac_kw'])
    return {**selected, 'target_ac_kw': target_ac_kw, 'electrical_compatibility_verified': False}

def estimate_generation(data, solar, panels):
    return [panels['installed_kwp'] * psh * days * data['performance_ratio'] for psh, days in zip(data['monthly_psh'], solar['days_per_month'])]

def estimate_finance(data, panels, inverter, monthly_generation):
    if panels['selected_count'] == 0 or inverter is None:
        return None
    panel_cost = panels['selected_count'] * data['panel_price_aud']
    total_cost = panel_cost + inverter['price_aud'] + data['bos_cost_aud']
    monthly_demand = data['monthly_consumption_kwh']
    annual_demand = monthly_demand * 12
    annual_generation = sum(monthly_generation)
    bill_before = annual_demand * data['import_tariff_aud']
    scenarios = []
    for ratio in data['self_consumption_ratios']:
        monthly_used = [min(energy * ratio, monthly_demand) for energy in monthly_generation]
        used = sum(monthly_used)
        surplus = annual_generation - used
        exported = surplus if data['export_enabled'] else 0
        curtailed = 0 if data['export_enabled'] else surplus
        remaining_imports = annual_demand - used
        bill_after = remaining_imports * data['import_tariff_aud']
        bill_reduction = bill_before - bill_after
        export_income = exported * data['export_tariff_aud']
        net_savings = bill_reduction + export_income - data['annual_maintenance_aud']
        payback = total_cost / net_savings if net_savings > 0 else None
        scenarios.append({'assumed_ratio': ratio, 'effective_ratio': used / annual_generation if annual_generation else 0, 'self_used_kwh': used, 'grid_imports_kwh': remaining_imports, 'exported_kwh': exported, 'curtailed_kwh': curtailed, 'solar_coverage': used / annual_demand, 'bill_before_aud': bill_before, 'bill_after_aud': bill_after, 'gross_bill_savings_aud': bill_reduction, 'bill_savings_percent': bill_reduction / bill_before * 100 if bill_before else 0, 'export_income_aud': export_income, 'annual_net_savings_aud': net_savings, 'simple_payback_years': payback, 'monthly_used_kwh': monthly_used})
    return {'panel_cost_aud': panel_cost, 'inverter_cost_aud': inverter['price_aud'], 'bos_cost_aud': data['bos_cost_aud'], 'total_cost_aud': total_cost, 'status': 'illustrative_pending_electrical_design', 'scenarios': scenarios}

def size_system(data):
    validate(data)
    resource = prepare_solar(data)
    design = choose_panels(data, resource)
    candidate = choose_inverter(data, design)
    generation = estimate_generation(data, resource, design)
    finance_result = estimate_finance(data, design, candidate, generation)
    if design['selected_count'] == 0:
        status = 'no_panels_fit'
    elif candidate is None:
        status = 'no_capacity_candidate'
    else:
        status = 'preliminary_candidate'
    warnings = ['Synthetic/manual solar inputs; no NASA request is made.', 'PSH x PR approximation; no detailed shading, thermal or clipping simulation.', 'Inverter screening is capacity-only; electrical compatibility is unverified.', 'Financial scenarios assume monthly self-consumption ratios, flat tariffs and constant net savings.', 'Not installation approval or a guaranteed financial return.']
    if design['roof_limited']:
        warnings.append('Requested array exceeds roof area; outputs use the smaller alternative.')
    return {'currency': 'AUD', 'status': status, 'installation_ready': False, 'inputs_used': deepcopy(data), 'solar': resource, 'panels': design, 'inverter_candidate': candidate, 'monthly_generation_kwh': generation, 'annual_generation_kwh': sum(generation), 'finance': finance_result, 'warnings': warnings}
