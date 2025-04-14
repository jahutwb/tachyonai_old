import pytest
import numpy as np
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime

from backend.pool_image_item import PoolImageItem
from backend.genetic_pool import (
    get_random_pool, generate_pool_with_genetic_algorithm,
    get_random_images_as_pool_items, process_pool_generation,
    generate_children_by_combination
)
from backend.models import ImageTypeEnum, SessionStatusEnum


class TestPoolImageItem:
    def test_init(self):
        """Test initializing PoolImageItem"""
        item = PoolImageItem(id=1, successes=2, failures=3, origin="child")
        assert item.id == 1
        assert item.successes == 2
        assert item.failures == 3
        assert item.origin == "child"

    def test_to_dict(self):
        """Test converting PoolImageItem to dictionary"""
        item = PoolImageItem(id=1, successes=2, failures=3, origin="child")
        result = item.to_dict()
        assert result == {
            "id": 1,
            "successes": 2,
            "failures": 3,
            "origin": "child"
        }

    def test_from_dict(self):
        """Test creating PoolImageItem from dictionary"""
        data = {
            "id": 1,
            "successes": 2,
            "failures": 3,
            "origin": "child"
        }
        item = PoolImageItem.from_dict(data)
        assert item.id == 1
        assert item.successes == 2
        assert item.failures == 3
        assert item.origin == "child"

    def test_from_dict_minimal(self):
        """Test creating PoolImageItem from minimal dictionary"""
        data = {"id": 1}
        item = PoolImageItem.from_dict(data)
        assert item.id == 1
        assert item.successes == 0
        assert item.failures == 0
        assert item.origin == "random"  # Default value is "random"

    def test_from_parents(self):
        """Test creating PoolImageItem from parents"""
        # Test with one parent
        item1 = PoolImageItem.from_parents(id=10, parent_ids=[5])
        assert item1.id == 10
        assert item1.origin == "child_of_5"

        # Test with two parents
        item2 = PoolImageItem.from_parents(id=20, parent_ids=[5, 6])
        assert item2.id == 20
        assert item2.origin == "child_of_5_6"

    def test_from_noise(self):
        """Test creating PoolImageItem from noise"""
        item = PoolImageItem.from_noise(id=10, parent_id=5, attempt=2)
        assert item.id == 10
        assert item.origin == "child_of_5_noise_2"

    def test_is_child(self):
        """Test checking if item is a child"""
        item1 = PoolImageItem(id=1, origin="random")
        assert not item1.is_child()

        item2 = PoolImageItem(id=2, origin="child_of_5")
        assert item2.is_child()

    def test_get_parents(self):
        """Test getting parent IDs"""
        # Not a child
        item1 = PoolImageItem(id=1, origin="random")
        assert item1.get_parents() == []

        # One parent
        item2 = PoolImageItem(id=2, origin="child_of_5")
        assert item2.get_parents() == [5]

        # Two parents
        item3 = PoolImageItem(id=3, origin="child_of_5_6")
        assert item3.get_parents() == [5, 6]

        # Noise child
        item4 = PoolImageItem(id=4, origin="child_of_5_noise_2")
        assert item4.get_parents() == [5]

    def test_is_from_noise(self):
        """Test checking if item is from noise"""
        item1 = PoolImageItem(id=1, origin="random")
        assert not item1.is_from_noise()

        item2 = PoolImageItem(id=2, origin="child_of_5_6")
        assert not item2.is_from_noise()

        item3 = PoolImageItem(id=3, origin="child_of_5_noise_2")
        assert item3.is_from_noise()

    def test_get_noise_attempt(self):
        """Test getting noise attempt number"""
        item1 = PoolImageItem(id=1, origin="random")
        assert item1.get_noise_attempt() is None

        item2 = PoolImageItem(id=2, origin="child_of_5_noise_2")
        assert item2.get_noise_attempt() == 2


class TestGetRandomPool:
    def test_get_random_pool(self):
        """Test creating a random pool of images"""
        db = MagicMock()

        # Prepare test data
        mock_pos_images = [MagicMock(id=i) for i in range(10)]
        mock_neg_images = [MagicMock(id=i+100) for i in range(10)]

        # Mock database queries
        mock_query = MagicMock()
        db.query.return_value = mock_query

        # Mock filters
        mock_pos_filter = MagicMock()
        mock_neg_filter = MagicMock()

        # Set return values
        mock_pos_filter.limit.return_value.all.return_value = mock_pos_images[:6]
        mock_neg_filter.limit.return_value.all.return_value = mock_neg_images[:6]

        # Configure filter to recognize image type and return appropriate mock
        def filter_side_effect(*args, **kwargs):
            # First argument is ImageModel.type == ImageTypeEnum.POSITIVE/NEGATIVE
            if len(args) > 0 and hasattr(args[0], 'right') and hasattr(args[0].right, 'value'):
                if args[0].right.value == ImageTypeEnum.POSITIVE:
                    return mock_pos_filter
                else:
                    return mock_neg_filter
            # For other filters
            return MagicMock()

        mock_query.filter = MagicMock(side_effect=filter_side_effect)
        mock_pos_filter.order_by = MagicMock(return_value=mock_pos_filter)
        mock_neg_filter.order_by = MagicMock(return_value=mock_neg_filter)

        # Call the function being tested
        with patch('backend.genetic_pool.get_random_images_as_pool_items') as mock_get_random:
            # Mock the function to return pool items with IDs 0-5 for positive and 100-105 for negative
            mock_get_random.side_effect = lambda db, count, is_positive, exclude_ids: [
                PoolImageItem(id=i) for i in range(count)
            ] if is_positive else [
                PoolImageItem(id=i+100) for i in range(count)
            ]

            pos_pool, neg_pool = get_random_pool(db, 6)

            # Check if the returned pools have the correct length
            assert len(pos_pool) == 6
            assert len(neg_pool) == 6

            # Check image IDs
            pos_ids = [item["id"] for item in pos_pool]
            neg_ids = [item["id"] for item in neg_pool]

            # Check if returned IDs match our mocked lists
            assert pos_ids == [0, 1, 2, 3, 4, 5]
            assert neg_ids == [100, 101, 102, 103, 104, 105]

            # Basic verification
            assert pos_ids != neg_ids

            # Check if origin is set to "random"
            assert all(item["origin"] == "random" for item in pos_pool)
            assert all(item["origin"] == "random" for item in neg_pool)


class TestGeneratePoolWithGeneticAlgorithm:
    def test_no_embeddings(self):
        """Test generating pool when there are no embeddings"""
        db = MagicMock()
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session.pos_pool_json = [{"id": 1}, {"id": 2}]
        mock_session.neg_pool_json = [{"id": 101}, {"id": 102}]

        # Configure get_image_embeddings to return empty dict (no embeddings)
        with patch('backend.genetic_pool.get_image_embeddings', return_value={}), \
             patch('backend.genetic_pool.get_random_pool') as mock_get_random:

            mock_get_random.return_value = ([{"id": 3}], [{"id": 103}])

            pos_pool, neg_pool = generate_pool_with_genetic_algorithm(mock_session, db, 2)

            # Check if get_random_pool was called
            mock_get_random.assert_called_once_with(db, 2)

            # Check returned values
            assert pos_pool == [{"id": 3}]
            assert neg_pool == [{"id": 103}]

    def test_with_embeddings(self):
        """Test generating pool with embeddings"""
        db = MagicMock()
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session.pos_pool_json = [{"id": 1, "successes": 1}, {"id": 2}]
        mock_session.neg_pool_json = [{"id": 101, "failures": 1}, {"id": 102}]

        # Configure get_image_embeddings to return embeddings
        with patch('backend.genetic_pool.get_image_embeddings') as mock_get_embeddings, \
             patch('backend.genetic_pool.process_pool_generation') as mock_process_pool:

            mock_get_embeddings.side_effect = lambda db, ids: {id: [0.1, 0.2] for id in ids}
            mock_process_pool.side_effect = lambda db, pool, embeddings, is_positive, num_pairs: [
                PoolImageItem(id=3, origin="child") if is_positive else PoolImageItem(id=103, origin="child")
            ]

            pos_pool, neg_pool = generate_pool_with_genetic_algorithm(mock_session, db, 2)

            # Check if process_pool_generation was called
            assert mock_process_pool.call_count == 2

            # Check returned values
            assert len(pos_pool) == 1
            assert len(neg_pool) == 1
            assert pos_pool[0]["id"] == 3
            assert neg_pool[0]["id"] == 103
            assert pos_pool[0]["origin"] == "child"
            assert neg_pool[0]["origin"] == "child"


class TestProcessPoolGeneration:
    def test_process_pool_generation_no_faiss_index(self):
        """Test processing pool generation when FAISS index is not available"""
        db = MagicMock()
        pool_items = [{"id": 1}, {"id": 2}]
        embeddings = {1: [0.1, 0.2], 2: [0.3, 0.4]}

        with patch('backend.genetic_pool.get_faiss_index_manager') as mock_manager, \
             patch('backend.genetic_pool.get_random_images_as_pool_items') as mock_get_random:

            # Configure FAISS manager to return None for index
            mock_manager.return_value.get_index.return_value = (None, None, None)

            # Configure random images fallback
            mock_get_random.return_value = [PoolImageItem(id=10), PoolImageItem(id=11)]

            result = process_pool_generation(db, pool_items, embeddings, is_positive=True, num_pairs=2)

            # Check if get_random_images_as_pool_items was called
            mock_get_random.assert_called_once()

            # Check returned values
            assert len(result) == 2
            assert [item.id for item in result] == [10, 11]

    def test_process_pool_generation_case_a(self):
        """Test processing pool generation - case A (total_successes > num_pairs)"""
        db = MagicMock()
        pool_items = [
            {"id": 1, "successes": 2},
            {"id": 2, "successes": 3},
            {"id": 3, "successes": 1},
        ]
        embeddings = {1: [0.1], 2: [0.2], 3: [0.3]}

        with patch('backend.genetic_pool.get_faiss_index_manager') as mock_manager, \
             patch('backend.genetic_pool.generate_children_by_combination') as mock_generate_children:

            # Configure FAISS manager to return mock index
            mock_manager.return_value.get_index.return_value = (MagicMock(), MagicMock(), MagicMock())

            # Configure generate_children_by_combination
            mock_generate_children.return_value = []

            result = process_pool_generation(db, pool_items, embeddings, is_positive=True, num_pairs=2)

            # Check returned values - should have 2 images
            assert len(result) == 2
            # Both images should be "bought" (from last pool)
            assert all(item.origin == "bought" for item in result)
            # Images should have IDs 2 and 1 (sorted by success count)
            assert [item.id for item in result] == [2, 1]


class TestGenerateChildrenByCombination:
    def test_generate_children_by_combination(self):
        """Test generating children by combining parent embeddings"""
        db = MagicMock()
        parent_items = [
            PoolImageItem(1, successes=3),
            PoolImageItem(2, successes=1)
        ]
        embeddings = {
            1: [0.5, 0.5],
            2: [0.3, 0.3]
        }

        with patch('backend.genetic_pool._find_nearest_image_excluding') as mock_find_nearest:
            # Configure mocks
            mock_find_nearest.side_effect = [(10, 0.1), (11, 0.2)]

            # Mock the database query for images
            mock_image1 = MagicMock(id=10)
            mock_image2 = MagicMock(id=11)
            db.query.return_value.filter.return_value.first.side_effect = [mock_image1, mock_image2]

            result = generate_children_by_combination(
                db=db,
                parent_items=parent_items,
                count=2,
                embeddings=embeddings,
                faiss_index=MagicMock(),
                id_to_index=MagicMock(),
                index_to_id=MagicMock(),
                exclude_ids=[],
                previous_pool_ids=[]
            )

            # Check calls
            assert mock_find_nearest.call_count == 2

            # Check returned values
            assert len(result) == 2
            # Check child IDs
            assert [item.id for item in result] == [10, 11]
            # Check origin
            assert all("child" in item.origin for item in result)

    def test_generate_children_by_combination_single_parent(self):
        """Test generating children with only one parent (noise fallback)"""
        db = MagicMock()
        parent_items = [PoolImageItem(1, successes=1)]
        embeddings = {1: [0.5, 0.5]}

        with patch('backend.genetic_pool._find_nearest_image_excluding') as mock_find_nearest:
            # Configure mocks
            mock_find_nearest.return_value = (100, 0.3)

            # Mock the database query for images
            mock_image = MagicMock(id=100)
            db.query.return_value.filter.return_value.first.return_value = mock_image

            result = generate_children_by_combination(
                db=db,
                parent_items=parent_items,
                count=1,
                embeddings=embeddings,
                faiss_index=MagicMock(),
                id_to_index=MagicMock(),
                index_to_id=MagicMock(),
                exclude_ids=[],
                previous_pool_ids=[]
            )

            # Check calls
            assert mock_find_nearest.call_count == 1

            # Check returned values
            assert len(result) == 1
            assert result[0].id == 100
            assert "noise" in result[0].origin


class TestGetRandomImagesAsPoolItems:
    def test_get_random_images_as_pool_items(self):
        """Test getting random images as pool items"""
        db = MagicMock()
        mock_query = MagicMock()
        db.query.return_value = mock_query

        # Prepare mocked images
        mock_images = [MagicMock(id=i) for i in range(10)]

        # Configure filter chain returning images
        mock_query.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_images[:3]

        result = get_random_images_as_pool_items(db, count=3, is_positive=True, exclude_ids=[5, 6])

        # Check calls
        assert db.query.call_count == 1
        assert mock_query.filter.call_count == 1

        # Check returned values
        assert len(result) == 3
        assert [item.id for item in result] == [0, 1, 2]
        assert all(item.origin == "random" for item in result)

    def test_get_random_images_as_pool_items_not_enough(self):
        """Test getting random images when there aren't enough available"""
        db = MagicMock()
        mock_query = MagicMock()
        db.query.return_value = mock_query

        # Prepare mocked images - only 2 images
        mock_images = [MagicMock(id=i) for i in range(2)]

        # Configure filter chain returning images
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_images

        # Request 5 images, but only 2 are available
        result = get_random_images_as_pool_items(db, count=5, is_positive=True, exclude_ids=[])

        # Check calls
        assert db.query.call_count == 1

        # Check returned values - should get only 2 images
        assert len(result) == 2


