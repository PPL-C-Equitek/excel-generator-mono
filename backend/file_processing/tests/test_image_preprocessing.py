import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from PIL import Image

from file_processing.services.image_preprocessing import (
    apply_adaptive_thresholding,
    apply_thresholding,
    convert_to_grayscale,
    deskew_image,
    morphological_cleanup,
    normalize_contrast,
    preprocess_image,
    remove_noise,
    upscale_image,
    add_border_padding,
)

class TestImagePreprocessing(unittest.TestCase):

    def setUp(self):
        self.dummy_color_img = np.zeros((100, 100, 3), dtype=np.uint8)
        self.dummy_color_img[20:80, 20:80] = [255, 255, 255]

        self.dummy_gray_img = np.zeros((100, 100), dtype=np.uint8)
        self.dummy_gray_img[20:80, 20:80] = 255

    @patch("file_processing.services.image_preprocessing.cv2")
    def test_convert_to_grayscale_from_color(self, mock_cv2):
        mock_cv2.cvtColor.return_value = self.dummy_gray_img
        
        result = convert_to_grayscale(self.dummy_color_img)
        
        mock_cv2.cvtColor.assert_called_once_with(self.dummy_color_img, mock_cv2.COLOR_BGR2GRAY)
        self.assertTrue(np.array_equal(result, self.dummy_gray_img))

    @patch("file_processing.services.image_preprocessing.cv2")
    def test_convert_to_grayscale_already_gray(self, mock_cv2):
        result = convert_to_grayscale(self.dummy_gray_img)
        
        mock_cv2.cvtColor.assert_not_called()
        self.assertTrue(np.array_equal(result, self.dummy_gray_img))

    @patch("file_processing.services.image_preprocessing.cv2")
    def test_remove_noise(self, mock_cv2):
        mock_cv2.medianBlur.return_value = "blurred_img"
        from file_processing.services.ocr_config import NOISE_REMOVAL_KERNEL_SIZE
        
        result = remove_noise(self.dummy_gray_img)
        
        mock_cv2.medianBlur.assert_called_once_with(self.dummy_gray_img, NOISE_REMOVAL_KERNEL_SIZE)
        self.assertEqual(result, "blurred_img")

    @patch("file_processing.services.image_preprocessing.cv2")
    def test_apply_thresholding(self, mock_cv2):
        mock_cv2.threshold.return_value = (0, "thresholded_img")
        mock_cv2.THRESH_BINARY = 0
        mock_cv2.THRESH_OTSU = 8
        
        result = apply_thresholding(self.dummy_gray_img)
        
        mock_cv2.threshold.assert_called_once_with(self.dummy_gray_img, 0, 255, 8)
        self.assertEqual(result, "thresholded_img")

    @patch("file_processing.services.image_preprocessing.cv2")
    def test_normalize_contrast(self, mock_cv2):
        mock_clahe = MagicMock()
        mock_clahe.apply.return_value = "clahe_img"
        mock_cv2.createCLAHE.return_value = mock_clahe
        
        from file_processing.services.ocr_config import CLAHE_CLIP_LIMIT, CLAHE_TILE_GRID_SIZE
        
        result = normalize_contrast(self.dummy_gray_img)
        
        mock_cv2.createCLAHE.assert_called_once_with(
            clipLimit=CLAHE_CLIP_LIMIT,
            tileGridSize=CLAHE_TILE_GRID_SIZE
        )
        mock_clahe.apply.assert_called_once_with(self.dummy_gray_img)
        self.assertEqual(result, "clahe_img")

    @patch("file_processing.services.image_preprocessing.cv2")
    def test_deskew_image_not_enough_pixels(self, mock_cv2):
        blank_img = np.zeros((100, 100), dtype=np.uint8)
        
        result = deskew_image(blank_img)
        
        mock_cv2.minAreaRect.assert_not_called()
        self.assertTrue(np.array_equal(result, blank_img))

    @patch("file_processing.services.image_preprocessing.cv2")
    def test_deskew_image_small_angle(self, mock_cv2):
        mock_cv2.minAreaRect.return_value = (None, None, -0.2)
        
        result = deskew_image(self.dummy_gray_img)
        
        mock_cv2.getRotationMatrix2D.assert_not_called()
        self.assertTrue(np.array_equal(result, self.dummy_gray_img))

    @patch("file_processing.services.image_preprocessing.cv2")
    def test_deskew_image_large_angle(self, mock_cv2):
        mock_cv2.minAreaRect.return_value = (None, None, -20)
        
        result = deskew_image(self.dummy_gray_img)
        
        mock_cv2.getRotationMatrix2D.assert_not_called()
        self.assertTrue(np.array_equal(result, self.dummy_gray_img))

    @patch("file_processing.services.image_preprocessing.cv2")
    def test_deskew_image_valid_angle(self, mock_cv2):
        mock_cv2.minAreaRect.return_value = (None, None, -5.0) 
        mock_cv2.getRotationMatrix2D.return_value = "rotation_matrix"
        mock_cv2.warpAffine.return_value = "rotated_img"
        mock_cv2.INTER_CUBIC = 2
        mock_cv2.BORDER_REPLICATE = 1
        
        result = deskew_image(self.dummy_gray_img)
        
        mock_cv2.getRotationMatrix2D.assert_called_once_with((50, 50), 5.0, 1.0)
        mock_cv2.warpAffine.assert_called_once_with(
            self.dummy_gray_img, "rotation_matrix", (100, 100),
            flags=2, borderMode=1
        )
        self.assertEqual(result, "rotated_img")

    @patch("file_processing.services.image_preprocessing.add_border_padding")
    @patch("file_processing.services.image_preprocessing.deskew_image")
    @patch("file_processing.services.image_preprocessing.morphological_cleanup")
    @patch("file_processing.services.image_preprocessing.apply_adaptive_thresholding")
    @patch("file_processing.services.image_preprocessing.remove_noise")
    @patch("file_processing.services.image_preprocessing.normalize_contrast")
    @patch("file_processing.services.image_preprocessing.convert_to_grayscale")
    @patch("file_processing.services.image_preprocessing.upscale_image")
    @patch("file_processing.services.image_preprocessing.cv2")
    def test_preprocess_image_pipeline(
        self, mock_cv2, mock_upscale, mock_gray, mock_clahe, mock_noise,
        mock_adaptive_thresh, mock_morph, mock_deskew, mock_border
    ):
        mock_upscale.return_value = self.dummy_color_img
        mock_gray.return_value = self.dummy_color_img
        mock_clahe.return_value = self.dummy_color_img
        mock_noise.return_value = self.dummy_color_img
        mock_adaptive_thresh.return_value = self.dummy_color_img
        mock_morph.return_value = self.dummy_color_img
        
        final_array = np.zeros((10, 10), dtype=np.uint8)
        mock_deskew.return_value = final_array
        mock_border.return_value = final_array
        
        pil_img = Image.fromarray(self.dummy_color_img)
        
        result = preprocess_image(pil_img)
        
        mock_upscale.assert_called_once()
        mock_gray.assert_called_once()
        mock_clahe.assert_called_once()
        mock_noise.assert_called_once()
        mock_adaptive_thresh.assert_called_once()
        mock_morph.assert_called_once()
        mock_deskew.assert_called_once()
        mock_border.assert_called_once()
        
        self.assertIsInstance(result, Image.Image)
        self.assertTrue(np.array_equal(np.array(result), final_array))
