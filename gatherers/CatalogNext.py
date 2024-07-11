from .Gatherer import Gatherer


class CatalogNext(Gatherer):
    def __init__(self):
        super().__init__()

    def gather(self):
        url = 'https://git.door43.org/api/v1/catalog/search'
        catalog_data = self._get_json_from_url(url)

        lst_gls = list()
        dict_identifiers = dict()
        dict_subjects = dict()
        dict_bp_collector = dict()

        lst_owner_ignore = ["test_org", "test_org2", "test_org3"]

        all_resources = 0
        for item in catalog_data["data"]:

            if item["owner"] in lst_owner_ignore:
                # Skip items from 'junk' owners ('test' or otherwise)
                continue

            all_resources += 1

            language = item["language"]

            if language not in lst_gls and item["language_is_gl"] is True:
                lst_gls.append(language)

            # 1) Resources by identifier
            lst_identifier = item["name"].lower().split("_")
            if len(lst_identifier) == 2:
                identifier = lst_identifier[1]
            else:
                identifier = lst_identifier[0]

            if identifier not in dict_identifiers:
                dict_identifiers[identifier] = 1
            else:
                dict_identifiers[identifier] += 1

            # 2) Resources by subject
            subject = item["subject"]
            if subject not in dict_subjects:
                dict_subjects[subject] = 1
            else:
                dict_subjects[subject] += 1

            # 3) Book package fact collecting
            if language not in dict_bp_collector:
                dict_bp_collector[language] = {"has_ta": False,
                                               "has_tw": False,
                                               "has_tn": False,
                                               "has_tq": False,
                                               "aligned_books": list()
                                               }

            # 3a) GL or not
            dict_bp_collector[language]["is_gl"] = item["language_is_gl"]

            # 3b) Check for Resources
            if identifier == "ta":
                dict_bp_collector[language]["has_ta"] = True
            elif identifier == "tw":
                dict_bp_collector[language]["has_tw"] = True
            elif identifier == "tn":
                dict_bp_collector[language]["has_tn"] = True
            elif identifier == "tq":
                dict_bp_collector[language]["has_tq"] = True

            # 3c) Check for Aligned Bible
            if item["subject"] == "Aligned Bible":
                for book in item["ingredients"]:
                    book_title = book["identifier"]

                    if book_title not in dict_bp_collector[language]["aligned_books"]:
                        if book["alignment_count"] > 0:
                            dict_bp_collector[language]["aligned_books"].append(book_title)

        # 4) Building the actual metrics dictionary
        metrics = dict()

        metrics["total_langs"] = len(dict_bp_collector)
        metrics["gls_with_content"] = len(lst_gls)

        # 4a) Resources by identifier
        for identifier in dict_identifiers:
            identifier_name = identifier.replace(' ', '_')
            metrics['resources_{}_langs'.format(identifier_name)] = dict_identifiers[identifier]

        # 4b) Resources by subject
        for subject in dict_subjects:
            subject_name = subject.replace(' ', '_')
            metrics['subject_{}'.format(subject_name)] = dict_subjects[subject]

        metrics["all_resources"] = len(catalog_data["data"])

        # 4c) Book (package) counting
        all_bpfs = 0
        for language in dict_bp_collector:
            item = dict_bp_collector[language]
            books_per_language = len(item["aligned_books"])

            # a) Book Package counting
            # If this language has a tA, a tN, a tQ, and a tW resource,
            # then, for every aligned book in the Aligned Bible for this language (contains the '\\zaln-s' tag),
            # we increment the number of completed Book Packages.
            if item["has_ta"] and item["has_tn"] and item["has_tq"] and item["has_tw"]:
                if books_per_language > 0:
                    all_bpfs += books_per_language

                    if item["is_gl"] is True:
                        metrics['completed_bps_per_language.gl.{}'.format(language)] = books_per_language
                    else:
                        metrics['completed_bps_per_language.ol.{}'.format(language)] = books_per_language

            # b) Book counting
            if item["is_gl"] is True:
                if 'completed_books.gl' not in metrics:
                    metrics['completed_books.gl'] = books_per_language
                else:
                    metrics['completed_books.gl'] += books_per_language
            else:
                if 'completed_books.ol' not in metrics:
                    metrics['completed_books.ol'] = books_per_language
                else:
                    metrics['completed_books.ol'] += books_per_language

            for book in item["aligned_books"]:
                if "completed_books.book." + book not in metrics:
                    metrics["completed_books.book." + book] = 1
                else:
                    metrics["completed_books.book." + book] += 1

        metrics['completed_bps'] = all_bpfs

        self._send_to_graphite('stats.gauges', 'catalog_next', metrics)
