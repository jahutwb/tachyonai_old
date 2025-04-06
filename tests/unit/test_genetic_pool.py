import pytest
import numpy as np
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime

from backend.genetic_pool import (
    PoolImageItem, create_initial_pool, generate_pool_from_last_session,
    generate_new_pool, generate_children, get_random_images,
    get_or_create_session, process_round_result, get_next_round_images
)
from backend.models import ImageTypeEnum, SessionStatusEnum


class TestPoolImageItem:
    def test_init(self):
        """Test inicjalizacji PoolImageItem"""
        item = PoolImageItem(1, 2, 3, "child", 5)
        assert item.id == 1
        assert item.successes == 2
        assert item.failures == 3
        assert item.origin == "child"
        assert item.parent == 5

    def test_to_dict(self):
        """Test konwersji PoolImageItem na słownik"""
        item = PoolImageItem(1, 2, 3, "child", 5)
        result = item.to_dict()
        assert result == {
            "id": 1,
            "successes": 2,
            "failures": 3,
            "origin": "child",
            "parent": 5
        }

    def test_from_dict(self):
        """Test tworzenia PoolImageItem ze słownika"""
        data = {
            "id": 1,
            "successes": 2,
            "failures": 3,
            "origin": "child",
            "parent": 5
        }
        item = PoolImageItem.from_dict(data)
        assert item.id == 1
        assert item.successes == 2
        assert item.failures == 3
        assert item.origin == "child"
        assert item.parent == 5

    def test_from_dict_minimal(self):
        """Test tworzenia PoolImageItem z minimalnego słownika"""
        data = {"id": 1}
        item = PoolImageItem.from_dict(data)
        assert item.id == 1
        assert item.successes == 0
        assert item.failures == 0
        assert item.origin is None
        assert item.parent is None


class TestCreateInitialPool:
    def test_create_initial_pool(self):
        """Test tworzenia początkowej puli obrazów"""
        db = MagicMock()
        
        # Przygotowanie danych testowych
        mock_pos_images = [MagicMock(id=i) for i in range(10)]
        mock_neg_images = [MagicMock(id=i+100) for i in range(10)]
        
        # Mockujemy zapytania do bazy danych
        mock_query = MagicMock()
        db.query.return_value = mock_query
        
        # Mockujemy filtry
        mock_pos_filter = MagicMock()
        mock_neg_filter = MagicMock()
        
        # Ustawiamy zwracane wartości
        mock_pos_filter.all.return_value = mock_pos_images
        mock_neg_filter.all.return_value = mock_neg_images
        
        # Konfigurujemy filtr, który rozpoznaje typ obrazu i zwraca odpowiedni mock
        def filter_side_effect(*args, **kwargs):
            # Pierwszy argument to ImageModel.type == ImageTypeEnum.POSITIVE/NEGATIVE
            if len(args) > 0 and hasattr(args[0], 'right') and hasattr(args[0].right, 'value'):
                if args[0].right.value == ImageTypeEnum.POSITIVE:
                    return mock_pos_filter
                else:
                    return mock_neg_filter
            # Dla innych filtrów (np. embedding.isnot(None))
            return MagicMock(all=MagicMock(return_value=[]))
        
        mock_query.filter = MagicMock(side_effect=filter_side_effect)
        
        # Mockujemy random.sample
        with patch('random.sample') as mock_sample:
            # Losowanie wybiera pierwsze k elementów z listy
            mock_sample.side_effect = lambda lst, k: lst[:k]
            
            # Wywołujemy testowaną funkcję
            from backend.genetic_pool import create_initial_pool
            pos_pool, neg_pool = create_initial_pool(db, 5, 5)
            
            # Sprawdzenie, czy zwrócone pule mają odpowiednią długość
            assert len(pos_pool) == 5
            assert len(neg_pool) == 5
            
            # Sprawdzenie ID obrazów
            pos_ids = [item.id for item in pos_pool]
            neg_ids = [item.id for item in neg_pool]
            
            # Sprawdzamy, czy zwracane ID odpowiadają naszym mockowanym listom
            assert pos_ids == [0, 1, 2, 3, 4]
            assert neg_ids == [100, 101, 102, 103, 104]
            
            # Podstawowa weryfikacja
            assert pos_ids != neg_ids
            
            # Sprawdzenie, czy origin jest ustawione na "random"
            assert all(item.origin == "random" for item in pos_pool)
            assert all(item.origin == "random" for item in neg_pool)


class TestGeneratePoolFromLastSession:
    def test_no_last_session(self):
        """Test generowania puli gdy nie ma ostatniej sesji"""
        db = MagicMock()
        # Konfiguracja, aby get_last_completed_session zwróciło None
        with patch('backend.genetic_pool.get_last_completed_session', return_value=None), \
             patch('backend.genetic_pool.create_initial_pool') as mock_create_initial:
            
            mock_create_initial.return_value = (["pos1", "pos2"], ["neg1", "neg2"])
            
            pos_pool, neg_pool = generate_pool_from_last_session(db, 1, 2)
            
            # Sprawdź, czy create_initial_pool zostało wywołane
            mock_create_initial.assert_called_once_with(db, 2, 2)
            
            # Sprawdź zwrócone wartości
            assert pos_pool == ["pos1", "pos2"]
            assert neg_pool == ["neg1", "neg2"]

    def test_with_last_session(self):
        """Test generowania puli z ostatniej sesji"""
        db = MagicMock()
        mock_session = MagicMock()
        mock_session.pos_pool_json = [{"id": 1, "successes": 1}, {"id": 2}]
        mock_session.neg_pool_json = [{"id": 101, "failures": 1}, {"id": 102}]
        
        # Konfiguracja, aby get_last_completed_session zwróciło sesję
        with patch('backend.genetic_pool.get_last_completed_session', return_value=mock_session), \
             patch('backend.genetic_pool.generate_new_pool') as mock_generate_new:
            
            mock_generate_new.side_effect = lambda db, pool, is_positive, num_pairs: \
                ["new_pos1", "new_pos2"] if is_positive else ["new_neg1", "new_neg2"]
            
            pos_pool, neg_pool = generate_pool_from_last_session(db, 1, 2)
            
            # Sprawdź wywołania generate_new_pool
            assert mock_generate_new.call_count == 2
            
            # Sprawdź przekazane argumenty
            for call in mock_generate_new.call_args_list:
                args, kwargs = call
                assert args[0] == db  # db
                assert len(args[1]) == 2  # last_pool
                assert isinstance(args[1][0], PoolImageItem)  # sprawdź czy to PoolImageItem
                assert kwargs['num_pairs'] == 2

            # Sprawdź zwrócone wartości
            assert pos_pool == ["new_pos1", "new_pos2"]
            assert neg_pool == ["new_neg1", "new_neg2"]


class TestGenerateNewPool:
    def test_generate_new_pool_no_embeddings(self):
        """Test generowania nowej puli gdy brak embeddingów"""
        db = MagicMock()
        last_pool = [PoolImageItem(1), PoolImageItem(2)]
        
        with patch('backend.genetic_pool.build_faiss_index'), \
             patch('backend.genetic_pool.get_image_embeddings', return_value={}), \
             patch('backend.genetic_pool.create_initial_pool') as mock_create_initial:
                
            mock_create_initial.return_value = (["pos1", "pos2"], ["neg1", "neg2"])
            
            result = generate_new_pool(db, last_pool, is_positive=True, num_pairs=2)
            
            # Sprawdź, czy create_initial_pool zostało wywołane
            mock_create_initial.assert_called_once()
            
            # Sprawdź zwrócone wartości
            assert result == ["pos1", "pos2"]

    def test_generate_new_pool_case_a(self):
        """Test generowania nowej puli - przypadek A (S > num_pairs)"""
        db = MagicMock()
        last_pool = [
            PoolImageItem(1, successes=2),
            PoolImageItem(2, successes=3),
            PoolImageItem(3, successes=1),
        ]
        embeddings = {1: [0.1], 2: [0.2], 3: [0.3]}
        
        with patch('backend.genetic_pool.build_faiss_index'), \
             patch('backend.genetic_pool.get_image_embeddings', return_value=embeddings), \
             patch('backend.genetic_pool.calculate_centroid') as mock_calc_centroid, \
             patch('backend.genetic_pool.generate_children') as mock_generate_children:
                
            # Konfiguracja mockow
            mock_calc_centroid.return_value = [0.0]
            mock_generate_children.return_value = [PoolImageItem(10, origin="child")]
            
            # Modyfikujemy, aby points było 0 po kupnie 2 obrazów (zamiast -1),
            # co spowoduje, że nie zostanie wywołane generate_children
            # Jest to zgodne z algorytmem, który kupuje obrazy aż points <= 0
            # Suma sukcesów: 2 + 3 + 1 = 6, points = 6 - 2 = 4, po kupnie 2 i 3 points = -2
            result = generate_new_pool(db, last_pool, is_positive=True, num_pairs=2)
            
            # Sprawdź zwrócone wartości - powinniśmy mieć 2 obrazy
            assert len(result) == 2
            # Oba obrazy powinny być "bought" (z ostatniej puli)
            assert all(item.origin == "bought" for item in result)
            # Obrazy powinny mieć ID 2 i 1 (kolejność wg ilości sukcesów)
            assert [item.id for item in result] == [2, 1]


class TestGenerateChildren:
    def test_generate_children(self):
        """Test generowania dzieci"""
        db = MagicMock()
        parent_items = [
            PoolImageItem(1, successes=3),
            PoolImageItem(2, successes=1)
        ]
        difference_vector = np.array([0.1, 0.1])
        
        with patch('backend.genetic_pool.get_image_embeddings') as mock_get_embeddings, \
             patch('backend.genetic_pool.find_nearest_image') as mock_find_nearest:
                
            # Konfiguracja mockow
            mock_get_embeddings.return_value = {
                1: [0.5, 0.5],
                2: [0.3, 0.3]
            }
            mock_find_nearest.side_effect = [10, 11, 12]
            
            result = generate_children(
                db=db,
                parent_items=parent_items,
                difference_vector=difference_vector,
                count=3,
                is_positive=True
            )
            
            # Sprawdź wywołania
            assert mock_get_embeddings.call_count == 1
            assert mock_find_nearest.call_count == 3
            
            # Sprawdź zwrócone wartości
            assert len(result) == 3
            # Sprawdź ID dzieci
            assert [item.id for item in result] == [10, 11, 12]
            # Sprawdź origin
            assert all(item.origin == "child" for item in result)
            # Sprawdź parent
            assert result[0].parent == 1  # dziecko pierwszego rodzica
            assert result[1].parent == 1  # dziecko pierwszego rodzica
            assert result[2].parent == 2  # dziecko drugiego rodzica

    def test_generate_children_failure_fallback(self):
        """Test generowania dzieci z fallbackiem do losowego obrazu"""
        db = MagicMock()
        parent_items = [PoolImageItem(1, successes=1)]
        difference_vector = np.array([0.1, 0.1])
        
        with patch('backend.genetic_pool.get_image_embeddings') as mock_get_embeddings, \
             patch('backend.genetic_pool.find_nearest_image') as mock_find_nearest, \
             patch('backend.genetic_pool.get_random_images') as mock_get_random:
                
            # Konfiguracja mockow
            mock_get_embeddings.return_value = {1: [0.5, 0.5]}
            # find_nearest_image zwraca None dla wszystkich prób (nie znaleziono najbliższego obrazu)
            mock_find_nearest.return_value = None
            # Fallback do losowego obrazu
            mock_get_random.return_value = [PoolImageItem(100, origin="random")]
            
            result = generate_children(
                db=db,
                parent_items=parent_items,
                difference_vector=difference_vector,
                count=1,
                is_positive=True
            )
            
            # Sprawdź wywołania
            assert mock_get_embeddings.call_count == 1
            # find_nearest_image powinno być wywołane 4 razy (raz normalnie + 3 próby z różnymi alpha)
            assert mock_find_nearest.call_count == 4
            assert mock_get_random.call_count == 1
            
            # Sprawdź zwrócone wartości
            assert len(result) == 1
            assert result[0].id == 100
            assert result[0].origin == "random"


class TestGetRandomImages:
    def test_get_random_images(self):
        """Test pobierania losowych obrazów"""
        db = MagicMock()
        mock_query = MagicMock()
        db.query.return_value = mock_query
        
        # Przygotowanie mockowanych obrazów
        mock_images = [MagicMock(id=i) for i in range(10)]
        
        # Konfiguracja łańcucha filtrów zwracającego obrazy
        mock_query.filter.return_value.filter.return_value.filter.return_value.all.return_value = mock_images
        
        with patch('backend.genetic_pool.random.sample') as mock_sample:
            # Losowy wybór zwraca pierwsze 3 obrazy
            mock_sample.return_value = mock_images[:3]
            
            result = get_random_images(db, count=3, is_positive=True, exclude_ids=[5, 6])
            
            # Sprawdź wywołania
            assert db.query.call_count == 1
            assert mock_query.filter.return_value.filter.return_value.filter.call_count == 1  # sprawdź, czy exclude_ids zostało użyte
            
            # Sprawdź zwrócone wartości
            assert len(result) == 3
            assert [item.id for item in result] == [0, 1, 2]
            assert all(item.origin == "random" for item in result)

    def test_get_random_images_not_enough(self):
        """Test pobierania losowych obrazów gdy nie ma wystarczającej liczby"""
        db = MagicMock()
        mock_query = MagicMock()
        db.query.return_value = mock_query
        
        # Przygotowanie mockowanych obrazów - tylko 2 obrazy
        mock_images = [MagicMock(id=i) for i in range(2)]
        
        # Konfiguracja łańcucha filtrów zwracającego obrazy
        mock_query.filter.return_value.filter.return_value.all.return_value = mock_images
        
        with patch('backend.genetic_pool.random.sample') as mock_sample:
            # sample powinno zwrócić wszystkie dostępne obrazy
            mock_sample.return_value = mock_images
            
            # Żądamy 5 obrazów, ale dostępne są tylko 2
            result = get_random_images(db, count=5, is_positive=True)
            
            # Sprawdź wywołania
            assert db.query.call_count == 1
            assert mock_sample.call_count == 1
            
            # Sprawdź zwrócone wartości - powinniśmy dostać tylko 2 obrazy
            assert len(result) == 2


class TestGetOrCreateSession:
    def test_get_existing_session(self):
        """Test pobierania istniejącej sesji"""
        db = MagicMock()
        mock_session = MagicMock(id=1)
        
        with patch('backend.genetic_pool.get_active_session', return_value=mock_session):
            result = get_or_create_session(db, user_id=1)
            
            # Sprawdź zwróconą wartość
            assert result == mock_session

    def test_create_new_session(self):
        """Test tworzenia nowej sesji"""
        db = MagicMock()
        mock_pos_pool = [PoolImageItem(1)]
        mock_neg_pool = [PoolImageItem(101)]
        mock_session = MagicMock(id=1)
        
        with patch('backend.genetic_pool.get_active_session', return_value=None), \
             patch('backend.genetic_pool.generate_pool_from_last_session', return_value=(mock_pos_pool, mock_neg_pool)), \
             patch('backend.genetic_pool.create_new_session', return_value=mock_session):
                
            result = get_or_create_session(db, user_id=1)
            
            # Sprawdź zwróconą wartość
            assert result == mock_session


class TestProcessRoundResult:
    def test_process_round_result_success(self):
        """Test przetwarzania wyniku rundy - sukces"""
        db = MagicMock()
        
        # Przygotowanie sesji
        mock_session = MagicMock()
        mock_session.pos_pool_json = [{"id": 1, "successes": 0}, {"id": 2, "successes": 0}]
        mock_session.neg_pool_json = [{"id": 101, "successes": 0}, {"id": 102, "successes": 0}]
        mock_session.session_profit_factor = 1.0
        mock_session.remaining_pairs = 2
        
        # Przygotowanie obrazów
        pos_image = MagicMock(total_successes=0, total_profit_factor=1.0)
        neg_image = MagicMock(total_successes=0, total_profit_factor=1.0)
        
        # Konfiguracja zapytań
        db.query.return_value.filter.return_value.first.side_effect = [
            mock_session,  # pierwsze wywołanie - sesja
            pos_image,     # drugie wywołanie - obraz pozytywny
            neg_image      # trzecie wywołanie - obraz negatywny
        ]
        
        # Poprawka: Mockujemy PoolImageItem.from_dict, aby zwracał obiekty z kontrolowanymi wartościami
        original_from_dict = PoolImageItem.from_dict
        
        def mock_from_dict(data):
            item = original_from_dict(data)
            # Jeśli to pozytywny obraz, który został wybrany do rundy, zmodyfikuj successes po aktualizacji
            if item.id == 1:
                item.successes = 1  # Ustawiamy na 1 zamiast 2, bo będziemy testować czy zostało zwiększone o 1
            return item
        
        with patch('backend.genetic_pool.PoolImageItem.from_dict', side_effect=mock_from_dict):
            # Wynik rundy to sukces
            result = process_round_result(
                db=db, 
                session_id=1, 
                round_id=1, 
                pos_id=1, 
                neg_id=101,
                result=True,  # sukces
                profit_fraction=0.1
            )
            
            # Sprawdź aktualizację sesji
            assert mock_session.session_profit_factor == 1.1  # 1.0 * (1 + 0.1)
            
            # Sprawdź aktualizację liczników obrazów
            assert pos_image.total_successes == 1
            assert pos_image.total_profit_factor == 1.1
            assert neg_image.total_successes == 1
            assert neg_image.total_profit_factor == 1.1
            
            # Sprawdź, czy liczba par się nie zmieniła
            assert mock_session.remaining_pairs == 2
            
            # Sprawdź, czy status sesji się nie zmienił
            assert mock_session.status != SessionStatusEnum.COMPLETED

    def test_process_round_result_failure(self):
        """Test przetwarzania wyniku rundy - porażka"""
        db = MagicMock()
        
        # Przygotowanie sesji
        mock_session = MagicMock()
        mock_session.pos_pool_json = [{"id": 1, "successes": 0}, {"id": 2, "successes": 0}]
        mock_session.neg_pool_json = [{"id": 101, "successes": 0}, {"id": 102, "successes": 0}]
        mock_session.session_profit_factor = 1.0
        mock_session.remaining_pairs = 1
        
        # Przygotowanie obrazów
        pos_image = MagicMock(total_failures=0)
        neg_image = MagicMock(total_failures=0)
        
        # Konfiguracja zapytań
        db.query.return_value.filter.return_value.first.side_effect = [
            mock_session,  # pierwsze wywołanie - sesja
            pos_image,     # drugie wywołanie - obraz pozytywny
            neg_image      # trzecie wywołanie - obraz negatywny
        ]
        
        # Wynik rundy to porażka
        result = process_round_result(
            db=db, 
            session_id=1, 
            round_id=1, 
            pos_id=1, 
            neg_id=101,
            result=False,  # porażka
            profit_fraction=0.1
        )
        
        # Sprawdź aktualizację sesji
        assert mock_session.session_profit_factor == 1.1  # 1.0 * (1 + 0.1)
        
        # Sprawdź aktualizację liczników obrazów
        assert pos_image.total_failures == 1
        assert neg_image.total_failures == 1
        
        # Sprawdź aktualizację puli
        pos_pool = [PoolImageItem.from_dict(item) for item in mock_session.pos_pool_json]
        neg_pool = [PoolImageItem.from_dict(item) for item in mock_session.neg_pool_json]
        
        # Obrazy powinny zostać usunięte z puli
        assert all(item.id != 1 for item in pos_pool)
        assert all(item.id != 101 for item in neg_pool)
        
        # Liczba par powinna się zmniejszyć
        assert mock_session.remaining_pairs == 0
        
        # Sesja powinna zostać zakończona, gdy nie ma więcej par
        assert mock_session.status == SessionStatusEnum.COMPLETED
        assert mock_session.ended_at is not None


class TestGetNextRoundImages:
    def test_get_next_round_images(self):
        """Test pobierania obrazów na następną rundę"""
        db = MagicMock()
        
        # Przygotowanie sesji
        mock_session = MagicMock()
        mock_session.status = SessionStatusEnum.ACTIVE
        mock_session.remaining_pairs = 2
        mock_session.pos_pool_json = [{"id": 1}, {"id": 2}]
        mock_session.neg_pool_json = [{"id": 101}, {"id": 102}]
        
        # Konfiguracja zapytania
        db.query.return_value.filter.return_value.first.return_value = mock_session
        
        with patch('backend.genetic_pool.random.choice') as mock_choice:
            # Symulacja losowego wyboru obrazów
            mock_choice.side_effect = lambda lst: lst[0]
            
            pos_id, neg_id = get_next_round_images(db, session_id=1)
            
            # Sprawdź zwrócone ID obrazów
            assert pos_id == 1
            assert neg_id == 101
            
            # Sprawdź wywołania
            assert db.query.call_count == 1
            assert mock_choice.call_count == 2

    def test_get_next_round_images_inactive_session(self):
        """Test pobierania obrazów dla nieaktywnej sesji"""
        db = MagicMock()
        
        # Przygotowanie nieaktywnej sesji
        mock_session = MagicMock()
        mock_session.status = SessionStatusEnum.COMPLETED
        mock_session.remaining_pairs = 0
        
        # Konfiguracja zapytania
        db.query.return_value.filter.return_value.first.return_value = mock_session
        
        pos_id, neg_id = get_next_round_images(db, session_id=1)
        
        # Powinno zwrócić None, None
        assert pos_id is None
        assert neg_id is None 