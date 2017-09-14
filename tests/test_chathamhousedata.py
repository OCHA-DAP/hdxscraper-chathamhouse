#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Unit tests for Chatham House data.

'''
from os.path import join, abspath

import pytest
import six

from chathamhouse.chathamhousedata import get_worldbank_iso2_to_iso3, get_camp_non_camp_populations, \
    get_worldbank_series, get_slumratios
from tests.expected_results import unhcr_non_camp_expected, unhcr_camp_expected, slum_ratios_expected


class TestChathamHouseData:
    @pytest.fixture(scope='function')
    def downloader(self):
        class Response:
            @staticmethod
            def json():
                pass

        class Download:
            @staticmethod
            def download(url):
                response = Response()
                if url == 'http://lala/countries/all/indicators/SP.URB.TOTL.IN.ZS?MRV=1&format=json&per_page=10000':
                    def fn():
                        return [None, [{'value': '58.0939285510597', 'date': '2016', 'indicator': {'value': 'Urban population (% of total)', 'id': 'SP.URB.TOTL.IN.ZS'}, 'country': {'value': 'Arab World', 'id': '1A'}, 'decimal': '0'},
                                       {'value': '66.032', 'date': '2016', 'indicator': {'value': 'Urban population (% of total)', 'id': 'SP.URB.TOTL.IN.ZS'}, 'country': {'value': 'Austria', 'id': 'AT'}, 'decimal': '0'},
                                       {'value': '32.277', 'date': '2016', 'indicator': {'value': 'Urban population (% of total)', 'id': 'SP.URB.TOTL.IN.ZS'}, 'country': {'value': 'Zimbabwe', 'id': 'ZW'}, 'decimal': '0'}]]
                    response.json = fn
                elif url == 'http://haha/countries?format=json&per_page=10000':
                    def fn():
                        return [{'per_page': '10000', 'pages': 1, 'page': 1, 'total': 304},
                                [{'name': 'Aruba', 'region': {'value': 'Latin America & Caribbean ', 'id': 'LCN'},
                                  'capitalCity': 'Oranjestad', 'id': 'ABW',
                                  'lendingType': {'value': 'Not classified', 'id': 'LNX'},
                                  'adminregion': {'value': '', 'id': ''}, 'iso2Code': 'AW', 'longitude': '-70.0167',
                                  'incomeLevel': {'value': 'High income', 'id': 'HIC'}, 'latitude': '12.5167'},
                                 {'name': 'Afghanistan', 'region': {'value': 'South Asia', 'id': 'SAS'},
                                  'capitalCity': 'Kabul', 'id': 'AFG', 'lendingType': {'value': 'IDA', 'id': 'IDX'},
                                  'adminregion': {'value': 'South Asia', 'id': 'SAS'}, 'iso2Code': 'AF',
                                  'longitude': '69.1761', 'incomeLevel': {'value': 'Low income', 'id': 'LIC'},
                                  'latitude': '34.5228'},
                                 {'name': 'Africa', 'region': {'value': 'Aggregates', 'id': 'NA'},
                                  'capitalCity': '', 'id': 'AFR',
                                  'lendingType': {'value': 'Aggregates', 'id': ''},
                                  'adminregion': {'value': '', 'id': ''}, 'iso2Code': 'A9', 'longitude': '',
                                  'incomeLevel': {'value': 'Aggregates', 'id': 'NA'}, 'latitude': ''},
                                 {'name': 'Angola', 'region': {'value': 'Sub-Saharan Africa ', 'id': 'SSF'},
                                  'capitalCity': 'Luanda', 'id': 'AGO', 'lendingType': {'value': 'IBRD', 'id': 'IBD'},
                                  'adminregion': {'value': 'Sub-Saharan Africa (excluding high income)', 'id': 'SSA'},
                                  'iso2Code': 'AO', 'longitude': '13.242',
                                  'incomeLevel': {'value': 'Upper middle income', 'id': 'UMC'},
                                  'latitude': '-8.81155'}]]
                    response.json = fn
                return response
        return Download()

    def test_get_worldbank_iso2_to_iso3(self, downloader):
        result = get_worldbank_iso2_to_iso3('http://haha/countries?format=json&per_page=10000', downloader)
        assert result == {'AF': 'afg', 'AO': 'ago', 'AW': 'abw'}

    def test_get_camp_non_camp_populations(self, datasets):
        unhcr_non_camp, unhcr_camp = get_camp_non_camp_populations('individual,undefined', 'self-settled,planned,collective,reception', datasets)
        assert unhcr_non_camp == unhcr_non_camp_expected
        assert unhcr_camp == unhcr_camp_expected

    def test_get_worldbank_series(self, downloader):
        result = get_worldbank_series('http://lala/countries/all/indicators/SP.URB.TOTL.IN.ZS?MRV=1&format=json&per_page=10000',
                                      downloader, {'AT': 'aut', 'ZW': 'zwe'})
        assert result == {'aut': 0.66032, 'zwe': 0.32277}

    def test_get_slumratios(self):
        def path2url(path):
            return six.moves.urllib_parse.urljoin("file://", six.moves.urllib.request.pathname2url(path))

        url = path2url(abspath(join('tests', 'fixtures', 'MDG_Export_20170913_174700805.zip')))
        result = get_slumratios(url)
        assert result == slum_ratios_expected