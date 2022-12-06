from .Gatherer import Gatherer
import mysql.connector


class TX(Gatherer):
    def __init__(self):
        super().__init__()

        mysql_host = self._get_env('MYSQL_HOST')
        mysql_user = self._get_env('MYSQL_USER')
        mysql_password = self._get_env('MYSQL_PASSWORD')
        mysql_ca_cert = self._get_env('MYSQL_SSL_CA_FILE')

        self.db = mysql.connector.connect(host=mysql_host, user=mysql_user, password=mysql_password,
                                          ssl_ca=mysql_ca_cert, ssl_verify_cert=True)

        self.stage = self._get_env('STAGE')

    def __get_langs_from_tx_db(self):
        sql_query = \
            'SELECT' \
            '   `lc`' \
            'FROM' \
            '   `tx`.`api`'

        curr_conn = self.db.cursor()
        curr_conn.execute(sql_query)

        lc_raw = curr_conn.fetchall()
        lc_langs = [lc[0] for lc in lc_raw]

        return lc_langs

    def __get_languages_from_td_api(self):
        langnames = self._get_json_from_url('https://td.unfoldingword.org/exports/langnames.json')
        lst_lcs = [lang['lc'] for lang in langnames]

        return lst_lcs

    def gather(self):
        metrics = dict()

        # Get list of 'allowed languages' from TD api
        lc_td = self.__get_languages_from_td_api()

        # Get lcs from tx DB
        lc_tx = self.__get_langs_from_tx_db()
        metrics['languages_all'] = len(lc_tx)

        # Find lcs that occur in both lists (where TD is probably leading)
        lc_valid = list(set(lc_tx) & set(lc_td))
        metrics['languages_valid'] = len(lc_valid)

        self._send_to_graphite('stats.gauges', 'tx.' + self.stage, metrics)
