import unittest

from normalizer import clean_persons, parse_date, parser
from engine import render_archive_citation, render_legislation_citation

try:
    from engine import (
        DEFAULT_CSL_PATH,
        format_head_author,
        generate_gost_bibliography,
        render_single_citation,
    )
    HAS_CITEPROC = True
except ImportError:
    HAS_CITEPROC = False


class TestNormalizer(unittest.TestCase):
    def test_parse_date_formats(self):
        self.assertEqual(parse_date("20.08.2026"), {"date-parts": [[2026, 8, 20]]})
        self.assertEqual(parse_date("20/08/2026"), {"date-parts": [[2026, 8, 20]]})
        self.assertEqual(parse_date("2026-08-20"), {"date-parts": [[2026, 8, 20]]})
        self.assertEqual(parse_date("2026, 8, 20"), {"date-parts": [[2026, 8, 20]]})
        self.assertEqual(parse_date([20, 8, 2026]), {"date-parts": [[2026, 8, 20]]})
        self.assertEqual(parse_date(2020), {"date-parts": [[2020]]})
        self.assertIsNone(parse_date("2026-99-99"))

    def test_clean_persons_initials(self):
        self.assertEqual(
            clean_persons("Бовыкин Д.Ю., Чудинов А.В."),
            [
                {"family": "Бовыкин", "given": "Д. Ю."},
                {"family": "Чудинов", "given": "А. В."},
            ],
        )
        self.assertEqual(
            clean_persons([{"family": "Guiomar", "given": "J.-Y."}]),
            [{"family": "Guiomar", "given": "J.-Y."}],
        )

    def test_page_range_dash(self):
        item = parser({"type": "chapter", "title": "Test", "page": "15-25"})
        self.assertEqual(item["page"], "15–25")


class TestArchiveAndLegislation(unittest.TestCase):
    def test_archive_full_name_and_abbr(self):
        data = parser({
            "type": "archive",
            "archive_name": "Государственный архив Иркутской области",
            "archive_abbr": "ГАИО",
            "archive_fond": "33",
            "archive_opis": "1",
            "archive_delo": "108",
            "archive_list": "23",
        })
        self.assertEqual(
            render_archive_citation(data),
            "Государственный архив Иркутской области (ГАИО). Ф. 33. Оп. 1. Д. 108. Л. 23.",
        )

    def test_archive_abbr_with_year_and_ob(self):
        data = parser({
            "type": "archive",
            "archive_name": "РГИА",
            "archive_fond": "1286",
            "archive_opis": "4",
            "archive_sub_unit": "1826",
            "archive_delo": "448",
            "archive_list": "18-19 об.",
        })
        self.assertEqual(
            render_archive_citation(data),
            "РГИА. Ф. 1286. Оп. 4. 1826. Д. 448. Л. 18–19 об.",
        )

    def test_legislation_federal_law(self):
        data = parser({
            "type": "legislation",
            "title": "Об общих принципах организации местного самоуправления в Российской Федерации",
            "law_type": "Федеральный закон",
            "law_number": "№ 131-ФЗ",
            "adoption_info": "принят Государственной думой 16 сентября 2003 года : одобрен Советом Федерации 24 сентября 2003 года",
            "publisher_place": "Москва",
            "publisher": "Проспект",
            "year": "2017",
            "number_of_pages": "158",
        })
        expected = (
            "Об общих принципах организации местного самоуправления в Российской Федерации : "
            "Федеральный закон № 131-ФЗ : [принят Государственной думой 16 сентября 2003 года : "
            "одобрен Советом Федерации 24 сентября 2003 года]. – Москва : Проспект, 2017. – 158 с."
        )
        self.assertEqual(render_legislation_citation(data), expected)

    def test_legislation_repealed_electronic(self):
        data = parser({
            "type": "legislation",
            "title": "Об общих началах местного самоуправления и местного хозяйства в СССР",
            "law_type": "закон СССР от 09.04.1990 г.",
            "container_title": "Гарант : справочно-правовая система",
            "url": "https://base.garant.ru/6335644/",
            "accessed_date": "03.03.2022",
            "repealed": True,
        })
        expected = (
            "Об общих началах местного самоуправления и местного хозяйства в СССР : "
            "закон СССР от 09.04.1990 г. – Текст : электронный // Гарант : справочно-правовая система. "
            "– URL: https://base.garant.ru/6335644/ (дата обращения: 03.03.2022). – Утратил силу."
        )
        self.assertEqual(render_legislation_citation(data), expected)


@unittest.skipUnless(HAS_CITEPROC, "citeproc-py не установлен в этом окружении")
class TestGostRendering(unittest.TestCase):
    def test_head_author_helper(self):
        self.assertEqual(
            format_head_author([{"family": "Бовыкин", "given": "Д. Ю."}, {"family": "Чудинов", "given": "А. В."}]),
            "Бовыкин Д. Ю.",
        )
        self.assertEqual(
            format_head_author([{"family": "Богданов", "given": "Дмитрий Евгеньевич"}]),
            "Богданов Д. Е.",
        )
        self.assertEqual(
            format_head_author([{"family": "Caseneuve", "given": "P. de"}]),
            "Caseneuve P. de",
        )
        self.assertIsNone(
            format_head_author([{"family": f"Автор{i}", "given": "А."} for i in range(4)])
        )

    def test_russian_monograph_two_authors(self):
        data = parser({
            "type": "book",
            "language": "ru",
            "authors": [
                {"family": "Бовыкин", "given": "Д. Ю."},
                {"family": "Чудинов", "given": "А. В."},
            ],
            "title": "Французская революция",
            "publisher_place": "Москва",
            "publisher": "Альпина нон-фикшн",
            "year": 2020,
            "number_of_pages": "468",
            "collection_title": "Библиотека ПостНауки",
            "isbn": "978-5-91671-975-8",
        })
        result = render_single_citation(data, style_path=DEFAULT_CSL_PATH)
        expected = (
            "Бовыкин Д. Ю. Французская революция / Д. Ю. Бовыкин, А. В. Чудинов. "
            "– Москва : Альпина нон-фикшн, 2020. – 468 с. – (Библиотека ПостНауки). "
            "– ISBN 978-5-91671-975-8."
        )
        self.assertEqual(result, expected)

    def test_russian_monograph_four_authors(self):
        data = parser({
            "type": "book",
            "language": "ru",
            "authors": [
                {"family": "Говдя", "given": "В. В."},
                {"family": "Дегальцева", "given": "Ж. В."},
                {"family": "Чужинов", "given": "С. В."},
                {"family": "Шулепина", "given": "С. А."},
            ],
            "title": "Управленческий учет и контроль строительных материалов и конструкций : монография",
            "publisher_place": "Краснодар",
            "publisher": "КубГАУ",
            "year": 2017,
            "number_of_pages": "149",
        })
        result = render_single_citation(data, style_path=DEFAULT_CSL_PATH)
        self.assertTrue(result.startswith("Управленческий учет"))
        self.assertIn("/ В. В. Говдя, Ж. В. Дегальцева, С. В. Чужинов, С. А. Шулепина.", result)

    def test_french_chapter_guiomar(self):
        data = parser({
            "type": "chapter",
            "language": "fr",
            "authors": [{"family": "Guiomar", "given": "J.-Y."}],
            "title": "La Grande Nation, est-ce encore la Nation ?",
            "container_title": "Du Directoire au Consulat 2. L’intégration des citoyens dans la Grande Nation",
            "editors": [
                {"family": "Jessenne", "given": "J.-P."},
                {"family": "Bernet", "given": "J."},
                {"family": "Leuwers", "given": "H."},
            ],
            "publisher_place": "Villeneuve d’Ascq",
            "publisher": "Publications de l’Institut de recherches historiques du Septentrion",
            "year": 2000,
            "collection_title": "Histoire et littérature du Septentrion (IRHiS)",
            "isbn": "978-2-490296-03-3",
            "note": "Première partie. Quelle Grande Nation",
            "page": "15-25",
            "url": "https://books.openedition.org/irhis/1720",
            "accessed_date": "20.08.2026",
        })
        result = render_single_citation(data, style_path=DEFAULT_CSL_PATH)
        self.assertTrue(result.startswith("Guiomar J.-Y. La Grande Nation"))
        self.assertIn("sous la direction de J.-P. Jessenne, J. Bernet, H. Leuwers", result)
        self.assertIn("– Текст : электронный //", result)
        self.assertIn("URL: https://books.openedition.org/irhis/1720 (consulté le: 20/08/2026)", result)
        self.assertNotIn("AD", result)
        self.assertNotIn("под редакцией", result)
        self.assertNotIn("URL :", result)

    def test_russian_journal_article_electronic(self):
        data = parser({
            "type": "article-journal",
            "language": "ru",
            "authors": [{"family": "Нехаев", "given": "А."}],
            "title": "Что такое «Ортодоксальная теория и история идей»? Дисциплинарная новелла в критико-иронических тонах",
            "container_title": "Социологическое обозрение",
            "year": 2014,
            "issue": "1",
            "volume": "13",
            "page": "176-233",
            "url": "https://cyberleninka.ru/article/n/chto-takoe-ortodoksalnaya-teoriya-i-istoriya-idey-distsiplinarnaya-novella-v-kritiko-ironicheskih-tonah",
            "accessed_date": "21.08.2026",
        })
        result = render_single_citation(data, style_path=DEFAULT_CSL_PATH)
        self.assertTrue(result.startswith("Нехаев А. Что такое"))
        self.assertIn("– Текст : электронный // Социологическое обозрение", result)
        self.assertNotIn("электронный. //", result)
        self.assertIn("(дата обращения: 21.08.2026)", result)

    def test_thesis_punctuation(self):
        data = parser({
            "type": "thesis",
            "language": "ru",
            "authors": [{"family": "Богданов", "given": "Дмитрий Евгеньевич"}],
            "title": "Конец домината: от тетрархии к военному регентству на западе Римской империи (379-423 гг.) : специальность 07.00.03 «Всеобщая история» : диссертация на соискание степени кандидата исторических наук",
            "publisher": "Белгородский государственный национальный исследовательский университет",
            "publisher_place": "Белгород",
            "year": 2018,
            "number_of_pages": "210",
        })
        result = render_single_citation(data, style_path=DEFAULT_CSL_PATH)
        self.assertTrue(result.startswith("Богданов Д. Е. Конец домината"))
        self.assertIn("Белгород, 2018. – 210 с.", result)

    def test_newspaper_no_extra_dash(self):
        data = parser({
            "type": "article-newspaper",
            "language": "ru",
            "title": "De Venice",
            "container_title": "Gazzette de France",
            "issued": "1777-03-14",
            "issue": "21",
            "page": "94",
        })
        result = render_single_citation(data, style_path=DEFAULT_CSL_PATH)
        self.assertNotIn("– (№ 21)", result)
        self.assertIn("(№ 21)", result)

    def test_batch_sort_russian_before_foreign(self):
        fr_item = parser({
            "id": "fr1",
            "type": "book",
            "language": "fr",
            "authors": [{"family": "Caseneuve", "given": "P. de"}],
            "title": "La Catelogne françoise",
            "publisher_place": "Toulouse",
            "publisher": "Pierre Bosc",
            "year": 1644,
        })
        ru_item = parser({
            "id": "ru1",
            "type": "book",
            "language": "ru",
            "authors": [{"family": "Шартье", "given": "Р."}],
            "title": "Культурные истоки Французской революции",
            "publisher_place": "Москва",
            "publisher": "Искусство",
            "year": 2001,
        })
        items = generate_gost_bibliography([fr_item, ru_item], numbered=True)
        self.assertTrue(items[0].startswith("1. Шартье Р."))
        self.assertTrue(items[1].startswith("2. Caseneuve P. de"))


if __name__ == "__main__":
    unittest.main(verbosity=2)