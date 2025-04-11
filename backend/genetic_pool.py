import logging
import random
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import Image as ImageModel, ImageTypeEnum
from .faiss_manager import get_faiss_index_manager, _find_nearest_image_excluding
from .embedding import get_image_embeddings
from .pool_image_item import PoolImageItem  # 💡 Nowy import

logger = logging.getLogger("backend.genetic_pool")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = True


def generate_children_by_combination(
    db: Session,
    parent_items: List[PoolImageItem],
    count: int,
    embeddings: Dict[int, List[float]],
    faiss_index,
    id_to_index,
    index_to_id,
    exclude_ids: List[int],
    previous_pool_ids: List[int],
    noise_scale_base: float = 0.02
) -> List[PoolImageItem]:
    logger.info(f"🪪 Logger używany w generate_children_by_combination: {logger.name}")
    logger.info(f"Generowanie {count} dzieci z {len(parent_items)} rodziców przez kombinację embeddingów")

    exclude_ids = set(exclude_ids or [])
    exclude_ids.update(previous_pool_ids or [])
    exclude_ids.update([item.id for item in parent_items])
    children = []

    if len(parent_items) >= 2:
        weighted_pairs = []
        for i in range(len(parent_items)):
            for j in range(i + 1, len(parent_items)):
                a, b = parent_items[i], parent_items[j]
                weight = a.successes + b.successes
                if weight > 0:
                    weighted_pairs.append(((a.id, b.id), weight))

        if not weighted_pairs:
            logger.warning("Brak par z sukcesami.")
            return []

        used_pairs = set()
        pair_pool = [pair for pair, _ in weighted_pairs]
        pair_weights = [w for _, w in weighted_pairs]

        attempts = 0
        while len(children) < count and attempts < count * 10:
            unused_pairs = [pair for pair in pair_pool if pair not in used_pairs]
            weights = [w for (pair, w) in zip(pair_pool, pair_weights) if pair not in used_pairs]

            if not unused_pairs:
                unused_pairs = pair_pool
                weights = pair_weights
                used_pairs = set()

            id1, id2 = random.choices(unused_pairs, weights=weights, k=1)[0]
            used_pairs.add((id1, id2))

            emb1, emb2 = embeddings.get(id1), embeddings.get(id2)
            if emb1 is None or emb2 is None:
                logger.warning(f"Brak embeddingów dla pary ({id1}, {id2})")
                attempts += 1
                continue

            combined_vec = np.array(emb1) + np.array(emb2)
            combined_vec = combined_vec / np.linalg.norm(combined_vec)

            nearest_id, distance = _find_nearest_image_excluding(
                faiss_index, id_to_index, index_to_id, combined_vec.tolist(), exclude_ids=exclude_ids, top_k=10
            )

            if nearest_id and nearest_id not in exclude_ids:
                image = db.query(ImageModel).filter(ImageModel.id == nearest_id).first()
                if image:
                    child = PoolImageItem.from_parents(id=image.id, parent_ids=[id1, id2])
                    child.successes = 0
                    child.failures = 0
                    children.append(child)
                    exclude_ids.add(image.id)
                    logger.info(f"✓ Dodano dziecko {image.id} z pary ({id1}, {id2}), distance={distance:.4f}")
            else:
                logger.debug(f"✗ Para ({id1}, {id2}) — nearest_id={nearest_id} już był lub nie znaleziono")
            attempts += 1

    elif len(parent_items) == 1:
        logger.info("Tylko jeden rodzic – fallback z narastającym szumem")
        parent = parent_items[0]
        parent_emb = embeddings.get(parent.id)
        if parent_emb is None:
            logger.warning("Brak embeddingu jedynego rodzica.")
            return []

        for i in range(count):
            noise_scale = noise_scale_base * (i + 1)
            noise = np.random.normal(0, noise_scale, size=len(parent_emb))
            noisy_vec = np.array(parent_emb) + noise
            noisy_vec = noisy_vec / np.linalg.norm(noisy_vec)

            nearest_id, distance = _find_nearest_image_excluding(
                faiss_index, id_to_index, index_to_id, noisy_vec.tolist(), exclude_ids=exclude_ids, top_k=10
            )

            if nearest_id and nearest_id not in exclude_ids:
                image = db.query(ImageModel).filter(ImageModel.id == nearest_id).first()
                if image:
                    child = PoolImageItem.from_noise(id=image.id, parent_id=parent.id, attempt=i + 1)
                    children.append(child)
                    exclude_ids.add(image.id)
                    logger.info(f"✓ Dodano dziecko {image.id} z szumu (i={i+1}), distance={distance:.4f}")
            else:
                logger.debug(f"✗ Szum {i+1}: nearest_id={nearest_id} już użyty lub niepoprawny")

    return children


def get_random_images_as_pool_items(db: Session, count: int, is_positive: bool, exclude_ids: List[int]) -> List[PoolImageItem]:
    q = db.query(ImageModel).filter(ImageModel.type == (ImageTypeEnum.POSITIVE if is_positive else ImageTypeEnum.NEGATIVE))
    if exclude_ids:
        q = q.filter(~ImageModel.id.in_(exclude_ids))
    images = q.order_by(func.random()).limit(count).all()
    logger.info(f"Pobrano {len(images)} losowych obrazów (is_positive={is_positive})")
    return [PoolImageItem(id=img.id) for img in images]


def process_pool_generation(
    db: Session,
    pool_items: List[Dict[str, Any]],
    embeddings: Dict[int, List[float]],
    is_positive: bool,
    num_pairs: int
) -> List[PoolImageItem]:
    logger.info(f"Rozpoczynam generowanie puli {'pozytywnej' if is_positive else 'negatywnej'}")
    manager = get_faiss_index_manager()
    image_type = ImageTypeEnum.POSITIVE if is_positive else ImageTypeEnum.NEGATIVE
    faiss_index, id_to_index, index_to_id = manager.get_index(image_type)

    if faiss_index is None:
        logger.error(f"Brak indeksu FAISS dla typu {image_type}. Zwracam losową pulę.")
        return get_random_images_as_pool_items(db, num_pairs, is_positive, [])

    successful_items = [PoolImageItem.from_dict(item) for item in pool_items if item.get("successes", 0) > 0]
    total_successes = sum(item.successes for item in successful_items)
    previous_ids = [item["id"] for item in pool_items]
    new_pool = []
    exclude_ids = set(previous_ids)

    if total_successes > num_pairs:
        logger.info("Przypadek A: więcej sukcesów niż par.")
        points = total_successes - num_pairs
        for item in sorted(successful_items, key=lambda i: i.successes, reverse=True):
            new_pool.append(PoolImageItem(id=item.id, origin="bought", successes=0, failures=0))
            exclude_ids.add(item.id)
            points -= item.successes
            if points <= 0 or len(new_pool) >= num_pairs:
                break
        num_children = num_pairs - len(new_pool)
    else:
        logger.info("Przypadek B: mniej lub tyle samo sukcesów co par.")
        num_children = total_successes

    if num_children > 0 and successful_items:
        logger.info(f"Generowanie {num_children} dzieci...")
        children = generate_children_by_combination(
            db=db,
            parent_items=successful_items,
            count=num_children,
            embeddings=embeddings,
            faiss_index=faiss_index,
            id_to_index=id_to_index,
            index_to_id=index_to_id,
            exclude_ids=list(exclude_ids),
            previous_pool_ids=previous_ids
        )
        new_pool.extend(children)
        exclude_ids.update(c.id for c in children)

    if len(new_pool) < num_pairs:
        remaining = num_pairs - len(new_pool)
        logger.info(f"Uzupełniam pulę {remaining} losowymi obrazami")
        fallback = get_random_images_as_pool_items(db, remaining, is_positive, list(exclude_ids))
        new_pool.extend(fallback)

    logger.info(f"✓ Wygenerowano pulę ({len(new_pool)} obrazów):")
    for item in new_pool:
        logger.info(f" - ID {item.id}, origin={item.origin}")
    return new_pool


def get_random_pool(db: Session, num_pairs: int = 6) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    pos = get_random_images_as_pool_items(db, num_pairs, True, [])
    neg = get_random_images_as_pool_items(db, num_pairs, False, [])
    return [p.to_dict() for p in pos], [n.to_dict() for n in neg]


def generate_pool_with_genetic_algorithm(previous_session, db: Session, num_pairs: int = 6) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        logger.info(f"🔁 Start generowania puli na podstawie sesji {previous_session.id}")
        pos_pool = previous_session.pos_pool_json
        neg_pool = previous_session.neg_pool_json
        pos_ids = [i["id"] for i in pos_pool]
        neg_ids = [i["id"] for i in neg_pool]
        pos_embeddings = get_image_embeddings(db, pos_ids)
        neg_embeddings = get_image_embeddings(db, neg_ids)

        if not pos_embeddings or not neg_embeddings:
            logger.warning("Brak embeddingów – fallback na losowe.")
            return get_random_pool(db, num_pairs)

        pos_new = process_pool_generation(db, pos_pool, pos_embeddings, True, num_pairs)
        neg_new = process_pool_generation(db, neg_pool, neg_embeddings, False, num_pairs)

        return [p.to_dict() for p in pos_new], [n.to_dict() for n in neg_new]
    except Exception as e:
        logger.error(f"Błąd w generate_pool_with_genetic_algorithm: {e}")
        return get_random_pool(db, num_pairs)
