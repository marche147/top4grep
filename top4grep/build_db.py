from datetime import datetime
from pathlib import Path

import requests
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from bs4 import BeautifulSoup

from .utils import new_logger
from .db import Base, Paper
from .abstract import Abstracts

logger = new_logger("DB")
logger.setLevel('INFO')

CONFERENCES = ["NDSS", "IEEE S&P", "USENIX", "CCS", "OSDI", "PLDI", "SOSP"]
NAME_MAP = {
        "NDSS": "ndss",
        "IEEE S&P": "sp",
        "USENIX": "uss",
        "CCS": "ccs",
        "OSDI": "osdi",
        "PLDI": "pldi",
        "SOSP": "sosp",
        }
PACKAGE_DIR = Path(__file__).resolve().parent
DB_PATH = PACKAGE_DIR / "data" / "papers.db"

engine = sqlalchemy.create_engine(f'sqlite:///{str(DB_PATH)}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def save_paper(conf, year, title, authors, abstract):
    logger.debug(f'Adding paper {title} with abstract {abstract[:20]}...')
    session = Session()
    paper = Paper(conference=conf, year=year, title=title, authors=", ".join(authors), abstract=abstract)
    session.add(paper)
    session.commit()
    session.close()

def paper_exist(conf, year, title, authors, abstract):
    session = Session()
    paper = session.query(Paper).filter(Paper.conference==conf, Paper.year==year, Paper.title==title, Paper.abstract==abstract).first()
    session.close()
    return paper is not None

def remove_conf_papers(conf):
    session = Session()
    paper = session.query(Paper).filter(Paper.conference == conf).delete()
    session.commit()
    session.close()

def get_papers(name, year, build_abstract):
    cnt = 0
    conf = NAME_MAP[name]

    if build_abstract and name == "NDSS" and (year == 2018 or year == 2016):
        logger.warning(f"Skipping the abstract for NDSS {year} becuase the website does not contain abstracts.")
        extract_abstract = False
    else:
        extract_abstract = build_abstract
    try:
        r = requests.get(f"https://dblp.org/db/conf/{conf}/{conf}{year}.html")
        assert r.status_code == 200

        html = BeautifulSoup(r.text, 'html.parser')
        paper_htmls = html.find_all("li", {'class': "inproceedings"})
        for paper_html in paper_htmls:
            title = paper_html.find('span', {'class': 'title'}).text
            authors = [x.text for x in paper_html.find_all('span', {'itemprop': 'author'})]
            if extract_abstract:
                abstract = Abstracts[name].get_abstract(paper_html, title, authors)
            else:
                abstract = ''
            # insert the entry only if the paper does not exist
            if not paper_exist(name, year, title, authors, abstract):
                save_paper(name, year, title, authors, abstract)
            cnt += 1
    except Exception as e:
        logger.warning(f"Failed to obtain papers at {name}-{year}: {e}")

    logger.debug(f"Found {cnt} papers at {name}-{year}...")


def build_db(build_abstract, confs=[]):
    START_YEARS = {
            'PLDI': 2000,   # it started earlier but we skip those...
            'SOSP': 2000,   # also skip the early ones...
            }
    for conf in CONFERENCES:
        logger.info(f"Building paper DB for {conf}")
        if confs and conf not in confs:
            continue
        start_year = 2000
        if conf in START_YEARS:
            start_year = START_YEARS[conf]
        for year in range(start_year, datetime.now().year+1):
            get_papers(conf, year, build_abstract)

if __name__ == '__main__':
    logger.setLevel('DEBUG')
    for year in range(2000, datetime.now().year+1):
        get_papers('OSDI', year, True)
