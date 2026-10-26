# doctor_repository.py
# Database queries for doctors: search with filters and full profile by id.

from database.connection import get_connection

MAX_RESULTS = 10
MAX_NEED_DISTANCE = 0.45  # bios farther than this do not match the patient's problem (tested: matches ~0.32-0.43, unrelated ~0.49)

# Allowed sort options -> SQL. Only these strings can reach ORDER BY.
SORT_OPTIONS = {
    "rating": "d.rating DESC, d.review_count DESC",
    "fee_low": "d.consultation_fee ASC",
    "fee_high": "d.consultation_fee DESC",
    "experience": "d.experience_years DESC",
    "soonest": "next_available_at ASC NULLS LAST",
}


def search_doctors(
    specialty: str | None = None,
    city: str | None = None,
    area: str | None = None,
    gender: str | None = None,
    language: str | None = None,
    max_fee: int | None = None,
    min_rating: float | None = None,
    sort_by: str = "rating",
    need_vector: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Doctors matching all given filters. Filters left as None are ignored."""
    conditions = ["d.is_active"]
    params: dict = {"limit": min(limit, MAX_RESULTS)}

    if specialty:
        conditions.append("(s.name ILIKE %(specialty)s OR s.name_urdu = %(specialty_exact)s)")
        params["specialty"] = f"{specialty}%"   # starts with: "ENT" must not match "Dentist"%"
        params["specialty_exact"] = specialty
    if gender:
        conditions.append("d.gender = %(gender)s")
        params["gender"] = gender.lower()
    if language:
        conditions.append("EXISTS (SELECT 1 FROM unnest(d.languages) AS lang WHERE lang ILIKE %(language)s)")
        params["language"] = language
    if max_fee:
        conditions.append("d.consultation_fee <= %(max_fee)s")
        params["max_fee"] = max_fee
    if min_rating:
        conditions.append("d.rating >= %(min_rating)s")
        params["min_rating"] = min_rating

    # City and area belong to clinics, so check through the doctor's schedules
    location_conditions = []
    if city:
        location_conditions.append("ci.name ILIKE %(city)s")
        params["city"] = city
    if area:
        location_conditions.append("c.area ILIKE %(area)s")
        params["area"] = f"%{area}%"
    if location_conditions:
        conditions.append(f"""
            EXISTS (
                SELECT 1 FROM doctor_schedules ds
                JOIN clinics c  ON c.id = ds.clinic_id
                JOIN cities ci  ON ci.id = c.city_id
                WHERE ds.doctor_id = d.id AND {" AND ".join(location_conditions)}
            )
        """)

    # With a described problem, best-matching bios come first; otherwise use the chosen sort
    if need_vector:
        conditions.append("(d.about_embedding <=> %(need)s::vector) <= %(max_need_distance)s")
        params["need"] = need_vector
        params["max_need_distance"] = MAX_NEED_DISTANCE
        order_by = "d.about_embedding <=> %(need)s::vector"
    else:
        order_by = SORT_OPTIONS.get(sort_by, SORT_OPTIONS["rating"])

    query = f"""
        SELECT
            d.id,
            d.full_name,
            d.gender,
            s.name AS specialty,
            d.qualifications,
            d.experience_years,
            d.consultation_fee,
            d.rating::float AS rating,
            d.review_count,
            d.languages,
            (
                SELECT jsonb_agg(DISTINCT jsonb_build_object('clinic', c.name, 'area', c.area, 'city', ci.name))
                FROM doctor_schedules ds
                JOIN clinics c  ON c.id = ds.clinic_id
                JOIN cities ci  ON ci.id = c.city_id
                WHERE ds.doctor_id = d.id
            ) AS clinics,
            (
                SELECT MIN(sl.starts_at) FROM slots sl
                WHERE sl.doctor_id = d.id AND sl.status = 'available' AND sl.starts_at > now()
            ) AS next_available_at
        FROM doctors d
        JOIN specialties s ON s.id = d.specialty_id
        WHERE {" AND ".join(conditions)}
        ORDER BY {order_by}
        LIMIT %(limit)s
    """

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def get_doctor_profile(doctor_id: int) -> dict | None:
    """Full profile of one doctor with weekly schedule. None if not found."""
    query = """
        SELECT
            d.id,
            d.full_name,
            d.gender,
            s.name AS specialty,
            d.qualifications,
            d.experience_years,
            d.consultation_fee,
            d.rating::float AS rating,
            d.review_count,
            d.languages,
            d.about,
            d.review_summary,
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'clinic', c.name,
                        'area', c.area,
                        'city', ci.name,
                        'address', c.address,
                        'day_of_week', ds.day_of_week,
                        'start', to_char(ds.start_time, 'HH24:MI'),
                        'end', to_char(ds.end_time, 'HH24:MI')
                    )
                    ORDER BY ds.day_of_week, ds.start_time
                )
                FROM doctor_schedules ds
                JOIN clinics c  ON c.id = ds.clinic_id
                JOIN cities ci  ON ci.id = c.city_id
                WHERE ds.doctor_id = d.id
            ) AS weekly_schedule
        FROM doctors d
        JOIN specialties s ON s.id = d.specialty_id
        WHERE d.id = %(doctor_id)s AND d.is_active
    """

    with get_connection() as conn:
        return conn.execute(query, {"doctor_id": doctor_id}).fetchone()