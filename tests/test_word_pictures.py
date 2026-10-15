import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
try:
    import pygame
except ImportError:
    raise unittest.SkipTest("Word illustration tests need pygame")

from word_pictures import WordPictures
from words import WORDS


class WordPictureTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.pictures = WordPictures()

    def tearDown(self):
        pygame.quit()

    def test_common_words_have_specific_different_associations(self):
        examples = ("cat", "dog", "fish", "apple", "carrot", "house", "book", "sun", "rain", "happy", "jump", "three")
        images = []
        for word in examples:
            with self.subTest(word=word):
                picture = self.pictures.picture(word)
                self.assertIsNotNone(picture)
                self.assertGreater(picture.get_bounding_rect().width, 10)
                self.assertIs(self.pictures.picture(word), picture)
                images.append(pygame.image.tobytes(picture, "RGBA"))
        self.assertEqual(len(set(images)), len(examples))

    def test_first_curriculum_has_over_a_hundred_pictured_words(self):
        supported = [word for word in WORDS if self.pictures.picture(word["id"]) is not None]
        self.assertGreaterEqual(len(supported), 100)

    def test_unknown_words_do_not_get_random_misleading_pictures(self):
        surface = pygame.Surface((300, 250))
        self.assertFalse(self.pictures.draw(surface, "a completely unknown word", surface.get_rect()))
        self.assertIsNone(self.pictures.picture("a completely unknown word"))


if __name__ == "__main__":
    unittest.main()
