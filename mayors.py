#!/usr/bin/env python

"""
mayors.py - scrape information about US Mayors from usmayors.org
"""

import argparse
import logging
import csv
import json
from datetime import datetime
from os.path import splitext

import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.usmayors.org/mayors/meet-the-mayors/"

from states import ALL_STATES


CSV_FIELDS = '''
    name email phone bio_url img_url city state population
    city_site_url next_election'''.split()

def parse_phone(p):
    if p:
        p = p.replace('(','').replace(')', '').replace(' ', '-')
    return p

def get_mayors_for_state(state):
    payload = {"searchTerm": state}
    response = requests.post(
        url=SEARCH_URL,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "OpenSourceActivism.tech"
        }
    )
    response.raise_for_status()

    page = BeautifulSoup(response.text, 'html.parser')
    content = page.select_one('div.post-content')
    mayor_list = content.find_all('ul')
    if not mayor_list:
        logging.info(f'no mayors found for {state}')
        return []
    logging.info(f'found {len(mayor_list)} mayors for {state}')

    parsed_list = []
    for mayor_ul in mayor_list:
        for br in mayor_ul.find_all('br'):
            br.decompose() # delete from the tree

        items = mayor_ul.contents
        # set common data fields by index
        try:
            data = {
                # items[0] == \n
                'img_url': items[1]['src'],
                'name': items[2].string,
                'city': items[3].split(',')[0].strip(),
                'state': items[3].split(',')[1].strip(),
            }
        except IndexError:
            logging.error('unable to get common fields from', items)
            continue
        # match others by text prefix
        for item in items:
            if 'Population' in item:
                data['population'] = item.split(':')[1].replace(',', '')
            if 'Next Election Date' in item:
                next_election = item.split(':')[1].strip()
                parsed_next_election = datetime.strptime(next_election, "%m/%d/%Y") 
                data['next_election'] = parsed_next_election.strftime("%Y-%m-%d")

            # match links by text or protocol
            if item.name == 'a':
                if 'Web Site' in item:
                   data['city_site_url'] = item['href']
                elif 'Bio' in item:
                    data['bio_url'] = item['href']
                elif 'tel:' in item.get('href'):
                    data['phone'] = parse_phone(item.string)
                elif 'mailto:' in item.get('href'):
                    data['email'] = item.string
        parsed_list.append(data)
    return parsed_list

def get_mayors(states=ALL_STATES):
    for state in states:
        for mayor in get_mayors_for_state(state):
            yield mayor


def write_to_csv(mayors, out):
    w = csv.DictWriter(out, CSV_FIELDS)
    w.writeheader()
    for mayor in mayors:
        w.writerow(mayor)


def write_to_json(mayors, out):
    json.dump(list(mayors), out, indent=4)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Scrape US mayoral data from usmayors.org")

    parser.add_argument('out', type=argparse.FileType('w', encoding="UTF-8"),
                        default='-')
    parser.add_argument('--format', choices=['csv', 'json'])
    parser.add_argument('--state', nargs='*', default=ALL_STATES)
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                    action="store_true")

    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    # guess format from file extension
    if args.format is None:
        fn = args.out.name
        if fn != '<stdout>':
            _, ext = splitext(fn)
            args.format = ext[1:]
        else:
            args.format = 'csv'

    args.writer = {
        'csv': write_to_csv,
        'json': write_to_json,
    }[args.format]  # may KeyError if format is unrecognized

    return args

if __name__ == '__main__':
    args = parse_arguments()
    mayors = get_mayors(states=args.state)
    args.writer(mayors, args.out)
