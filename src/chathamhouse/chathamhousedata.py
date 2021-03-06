#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Chatham House Data
------------------

Collects input data for Chatham House.

"""
import logging

from hdx.data.dataset import Dataset
from hdx.data.resource import Resource
from hdx.data.showcase import Showcase
from hdx.utilities.dictandlist import integer_value_convert
from hdx.location.country import Country
from slugify import slugify


logger = logging.getLogger(__name__)


def append_value(countrydict, iso3, tier_or_type, name, value):
    tiers_or_types = countrydict.get(iso3)
    if tiers_or_types is None:
        tiers_or_types = dict()
        countrydict[iso3] = tiers_or_types
    camps = tiers_or_types.get(tier_or_type)
    if camps is None:
        camps = dict()
        tiers_or_types[tier_or_type] = camps
    existing_pop = camps.get(name)
    if existing_pop is None:
        existing_pop = 0
    camps[name] = existing_pop + value


def check_name_dispersed(name):
    lowername = name.lower()
    if 'dispersed' in lowername and ('country' in name.lower() or 'territory' in name.lower()):
        return True
    return False


def get_iso3(name):
    iso3, match = Country.get_iso3_country_code_fuzzy(name, exception=ValueError)
    if not match:
        logger.info('Country %s matched to ISO3: %s!' % (name, iso3))
    return iso3


def get_camp_non_camp_populations(noncamp_types, camp_types, camp_overrides, datasets, downloader):
    noncamp_types = noncamp_types.split(',')
    camp_types = camp_types.split(',')
    dataset_unhcr = None
    latest_date = None
    for dataset in datasets:
        if 'displacement' in dataset['title'].lower():
            date = dataset.get_dataset_date_as_datetime()
            if latest_date is None or date > latest_date:
                dataset_unhcr = dataset
                latest_date = date
    if dataset_unhcr is None:
        raise ValueError('No UNHCR dataset found!')
    url = dataset_unhcr.get_resources()[0]['url']
    country_ind = 0  # assume first column contains country
    iso3 = None
    row = None
    prev_row = None
    all_camps_per_country = dict()
    unhcr_non_camp = dict()
    unhcr_camp = dict()
    unhcr_camp_excluded = dict()
    rowiter = downloader.get_tabular_rows(url, sheet='Tab15')
    for row in rowiter:
        country = row[country_ind]
        iso3 = Country.get_iso3_country_code(country)
        if iso3 is not None:
            break
        prev_row = row
    accommodation_ind = None
    location_ind = None
    population_ind = None
    population = None
    for i, text in enumerate(prev_row):
        header = text.lower()
        value = row[i]
        if 'accommodation' in header:
            accommodation_ind = i
        elif 'location' in header and len(value) > 1:
            location_ind = i
        else:
            try:
                population = int(value)
                population_ind = i
                break
            except ValueError:
                pass
    campname = row[location_ind]

    def get_accommodation_type(name):
        accom_type = camp_overrides['Accommodation Type'].get(name)
        if accom_type is None:
            accom_type = row[accommodation_ind]
        else:
            logger.info('Overriding accommodation type to %s for %s' % (accom_type, name))
        return accom_type.lower()

    accommodation_type = get_accommodation_type(campname)

    def match_camp_types(name, accom_type, pop, iso):
        if check_name_dispersed(name):
            accom_type = noncamp_types[0]
        found_camp_type = None
        for camp_type in camp_types:
            if camp_type in accom_type:
                found_camp_type = camp_type
                unhcr_camp[name] = pop, iso, found_camp_type
                break
        for noncamp_type in noncamp_types:
            if noncamp_type in accom_type:
                found_camp_type = noncamp_type
                append_value(unhcr_non_camp, iso, found_camp_type, name, pop)
                break
        if found_camp_type is None:
            append_value(unhcr_camp_excluded, iso, accom_type, name, pop)
            append_value(all_camps_per_country, iso, accom_type, name, pop)
        else:
            append_value(all_camps_per_country, iso, found_camp_type, name, pop)

    match_camp_types(campname, accommodation_type, population, iso3)
    for row in rowiter:
        country = row[country_ind]
        if not country:
            continue
        if 'NOTES' in country.upper():
            break
        iso3, match = Country.get_iso3_country_code_fuzzy(country)
        if iso3 is None:
            logger.warning('Country %s could not be matched to ISO3 code!' % country)
            continue
        else:
            if match is False:
                logger.info('Matched %s to ISO3: %s!' % (country, iso3))
        campname = row[location_ind]
        accommodation_type = get_accommodation_type(campname)
        population = int(row[population_ind])
        match_camp_types(campname, accommodation_type, population, iso3)

    for campname in sorted(camp_overrides['Population']):
        if campname in unhcr_camp:
            continue
        iso3 = camp_overrides['Country'][campname]
        accommodation_type = camp_overrides['Accommodation Type'][campname].lower()
        population = camp_overrides['Population'][campname]
        logger.info('Adding camp from override: %s (%s, %s): %d' % (campname, iso3, accommodation_type, population))
        match_camp_types(campname, accommodation_type, population, iso3)

    return all_camps_per_country, unhcr_non_camp, unhcr_camp, unhcr_camp_excluded


def get_camptypes(url, downloader):
    camptypes = downloader.download_tabular_rows_as_dicts(url)
    for key in camptypes:
        camptypes[key] = integer_value_convert(camptypes[key])
    return camptypes


def get_camptypes_fallbacks(url, downloader, keyfn=lambda x: x):
    camptypes = downloader.download_tabular_rows_as_dicts(url)
    camptypes_offgrid = dict()
    camptypes_solid = dict()
    for key in camptypes:
        new_key = keyfn(key)
        camptypes_offgrid[new_key] = dict()
        camptypes_solid[new_key] = dict()
        for tier in camptypes[key]:
            try:
                typeval = int(camptypes[key][tier])
                if 'Lighting OffGrid' in tier:
                    camptypes_offgrid[new_key][tier.replace('Lighting OffGrid ', '')] = typeval
                else:
                    camptypes_solid[new_key][tier.replace('Cooking Solid ', '')] = typeval
            except ValueError:
                pass
    return camptypes_offgrid, camptypes_solid


def get_worldbank_series(json_url, downloader):
    response = downloader.download(json_url)
    json = response.json()
    data = dict()
    for countrydata in json[1]:
        iso3 = Country.get_iso3_from_iso2(countrydata['country']['id'])
        if iso3 is not None:
            value = countrydata.get('value')
            if value:
                data[iso3] = float(value) / 100.0
    return data


def get_slumratios(url, downloader):
    stream = downloader.get_tabular_stream(url, headers=1, format='csv', compression='zip')
    years = set()
    for header in stream.headers:
        try:
            int(header)
            years.add(header)
        except ValueError:
            pass
    years = sorted(years, reverse=True)
    slumratios = dict()
    for row in stream.iter(keyed=True):
        if not row:
            break
        iso3 = Country.get_iso3_from_m49(int(row['CountryCode']))
        if iso3 is None:
            continue
        for year in years:
            value = row.get(year)
            if value and value != ' ':
                slumratios[iso3] = float(value) / 100.0
    return slumratios


def generate_dataset_resources_and_showcase(pop_types, today):
    title = 'Energy consumption of refugees and displaced people'
    slugified_name = slugify(title.lower())

    dataset = Dataset({
        'name': slugified_name,
        'title': title,
    })
    dataset.set_maintainer('196196be-6037-4488-8b71-d786adf4c081')
    dataset.set_organization('0c6bf79f-504c-4ba5-9fdf-c8cc893c8b2f')
    dataset.set_dataset_date_from_datetime(today)
    dataset.set_expected_update_frequency('Every month')
    dataset.add_other_location('world')

    tags = ['HXL', 'energy', 'refugees', 'internally displaced persons - idp']
    dataset.add_tags(tags)

    resources = list()
    for pop_type in pop_types:
        resource_data = {
            'name': '%s_consumption.csv' % pop_type.lower().replace(' ', '_'),
            'description': '%s %s' % (pop_type, title.lower()),
            'format': 'csv'
        }
        resources.append(Resource(resource_data))

    resource_data = {
        'name': 'population.csv',
        'description': 'UNHCR displaced population totals',
        'format': 'csv'
    }
    resources.append(Resource(resource_data))

    resource_data = {
        'name': 'keyfigures_disagg.csv',
        'description': 'Disaggregated MEI Key Figures',
        'format': 'csv'
    }
    resources.append(Resource(resource_data))

    resource_data = {
        'name': 'keyfigures.csv',
        'description': 'MEI Key Figures',
        'format': 'csv'
    }
    resources.append(Resource(resource_data))

    showcase = Showcase({
        'name': '%s-showcase' % slugified_name,
        'title': 'Energy services for refugees and displaced people',
        'notes': 'Click the image on the right to go to the energy services model',
        'url': 'http://www.sciencedirect.com/science/article/pii/S2211467X16300396',
        'image_url': 'https://ars.els-cdn.com/content/image/X2211467X.jpg'
    })
    showcase.add_tags(tags)

    return dataset, resources, showcase
