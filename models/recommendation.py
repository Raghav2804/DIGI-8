"""Dataset-aware content matching for job recommendations."""
import re
import math

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

MAX_CANDIDATES = 8_000
TOKEN_RE = re.compile(r"[a-z0-9+#.]+", re.I)


def _text(value):
    if value is None or (not isinstance(value, (list, tuple, set)) and pd.isna(value)):
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(v) for v in value)
    return str(value).strip()


def _has_values(series):
    return series.fillna("").astype(str).str.strip().ne("").any()


def source_capabilities(df):
    """Report which user preferences can be evaluated against this dataset."""
    modes = df.remote_status.fillna("").astype(str).str.strip().str.lower()
    return {
        "skills": bool(_has_values(df.skills)),
        "description": bool(_has_values(df.description)),
        "experience": bool(_has_values(df.experience)),
        "location": bool(_has_values(df.location) or _has_values(df.country)),
        "employment_type": bool(_has_values(df.employment_type)),
        "work_mode": bool(modes.ne("").any() and not modes.isin(["unknown", "unspecified", "none", "nan"]).all()),
    }


def _similarities(documents, query):
    if not query or not any(doc.strip() for doc in documents):
        return [0.0] * len(documents)
    try:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=20_000)
        matrix = vectorizer.fit_transform(documents + [query])
        return cosine_similarity(matrix[-1], matrix[:-1]).ravel().tolist()
    except ValueError:
        return [0.0] * len(documents)


def recommend(df, profile, limit=20):
    """Rank imported jobs using only fields actually present in the source.

    TF-IDF compares the user's role and skill text to the available listing text.
    Structured experience, location, work mode, and employment filters contribute
    only when those fields contain real values. Missing source data is never
    treated as a positive match.
    """
    if df.empty:
        return []
    profile = profile or {}
    skills_query = _text(profile.get("skills"))
    title_query = _text(profile.get("job_title"))
    experience_query = _text(profile.get("experience"))
    location_query = _text(profile.get("location"))
    employment_query = _text(profile.get("employment_type"))
    work_query = _text(profile.get("work_mode"))
    query = " ".join(x for x in (skills_query, title_query) if x)
    if not query:
        raise ValueError("Enter at least one skill or a preferred job title.")

    titles = df.job_title.fillna("").map(_text)
    skills = df.skills.fillna("").map(_text)
    inferred_skills = df.inferred_skills.map(_text) if "inferred_skills" in df else pd.Series("", index=df.index)
    descriptions = df.description.fillna("").map(_text)
    listing_text = (titles + " " + skills + " " + inferred_skills + " " + descriptions).str.strip()

    # Retrieve all lexical candidates before ranking; filter generic prompt words
    # so terms such as "and" or "developer" do not swamp specific skill matches.
    tokens = [t for t in dict.fromkeys(TOKEN_RE.findall(query.lower()))
              if len(t) > 1 and t not in ENGLISH_STOP_WORDS]
    if tokens:
        pattern = "|".join(re.escape(t) for t in tokens)
        candidate_mask = listing_text.str.contains(pattern, case=False, regex=True, na=False)
        candidates = df.loc[candidate_mask].copy()
        if not candidates.empty and len(candidates) > MAX_CANDIDATES:
            candidate_text = listing_text.loc[candidates.index].str.lower()
            hits = candidate_text.apply(lambda value: sum(value.count(t) for t in tokens))
            candidates = candidates.loc[hits.sort_values(ascending=False, kind="stable").head(MAX_CANDIDATES).index]
    else:
        candidates = df.iloc[0:0].copy()
    if candidates.empty:
        # With no shared term, there is no evidence for a match. Return no
        # recommendations instead of presenting a random sample as relevant.
        return []

    capabilities = source_capabilities(df)
    roles_have_data = bool(title_query)
    structured_skills = capabilities["skills"]
    descriptions_have_data = capabilities["description"]
    has_experience = capabilities["experience"]
    has_location = capabilities["location"]
    has_employment = capabilities["employment_type"]
    has_work_mode = capabilities["work_mode"]

    requested_filters_available = capabilities
    if experience_query and has_experience:
        candidates = candidates[candidates.experience.fillna("").astype(str).str.contains(re.escape(experience_query), case=False, na=False)]
        if candidates.empty: return []
    if location_query and has_location:
        loc = candidates.location.fillna("").astype(str)
        country = candidates.country.fillna("").astype(str)
        candidates = candidates[loc.str.contains(re.escape(location_query), case=False, na=False) | country.str.contains(re.escape(location_query), case=False, na=False)]
        if candidates.empty: return []
    if employment_query and has_employment:
        candidates = candidates[candidates.employment_type.fillna("").astype(str).str.contains(re.escape(employment_query), case=False, na=False)]
    if work_query and has_work_mode:
        candidates = candidates[candidates.remote_status.fillna("").astype(str).str.contains(re.escape(work_query), case=False, na=False)]
    if candidates.empty:
        return []

    min_salary = _text(profile.get("min_salary"))
    if min_salary:
        try:
            floor = float(min_salary)
        except ValueError:
            raise ValueError("Minimum salary must be a number.") from None
        if not math.isfinite(floor) or floor < 0:
            raise ValueError("Minimum hourly rate must be a finite non-negative number.")
        salary = pd.to_numeric(candidates.salary, errors="coerce")
        is_hourly = candidates.salary_period.fillna("").astype(str).str.casefold().eq("hourly")
        # Other pay periods and project budgets cannot satisfy an hourly-rate floor.
        candidates = candidates.loc[is_hourly & salary.notna() & salary.ge(floor)]
        if candidates.empty:
            return []

    # Align vectors after any structured filtering using stable original indices.
    # Similarities are recomputed for this smaller result set to avoid index drift.
    titles = candidates.job_title.fillna("").map(_text)
    skills = candidates.skills.fillna("").map(_text)
    inferred_skills = candidates.inferred_skills.map(_text) if "inferred_skills" in candidates else pd.Series("", index=candidates.index)
    descriptions = candidates.description.fillna("").map(_text)
    listing_text = (titles + " " + skills + " " + inferred_skills + " " + descriptions).str.strip()
    role_scores = _similarities(titles.tolist(), title_query)
    # Keep title relevance and the skills/tags signal separate, otherwise the
    # same title words are counted twice in a profile that supplies both.
    skill_text = (skills + " " + inferred_skills + " " + descriptions).str.strip()
    skill_scores = _similarities(skill_text.tolist(), skills_query)

    out = []
    for pos, (_, row) in enumerate(candidates.iterrows()):
        components = []
        # Renormalize weights across usable evidence; don't award points for
        # fields absent from the actual dataset.
        if roles_have_data:
            components.append(("Role relevance", role_scores[pos], .55 if not structured_skills else .35))
        if skills_query:
            skill_weight = .30 if (structured_skills or descriptions_have_data) else .35
            components.append((("Skill text similarity" if structured_skills or descriptions_have_data else "Title-inferred tag similarity"), skill_scores[pos], skill_weight))
        if location_query and has_location:
            row_location = " ".join((_text(row.get("location")), _text(row.get("country")))).lower()
            components.append(("Location match", float(location_query.lower() in row_location), .15))
        if experience_query and has_experience:
            components.append(("Experience match", float(experience_query.lower() in _text(row.get("experience")).lower()), .10))
        if employment_query and has_employment:
            components.append(("Employment type match", float(employment_query.lower() in _text(row.get("employment_type")).lower()), .10))
        if work_query and has_work_mode:
            components.append(("Work arrangement match", float(work_query.lower() in _text(row.get("remote_status")).lower()), .10))
        weight_total = sum(weight for _, _, weight in components) or 1
        score = 100 * sum(value * weight for _, value, weight in components) / weight_total
        rec = row.where(row.notna(), None).to_dict()
        rec["job_key"] = str(row.get("apply_url") or f"{row.job_title}-{pos}")
        rec["match_percent"] = round(score)
        rec["reasons"] = [name for name, value, _ in components if value >= .15]
        rec["match_breakdown"] = {name: round(value * 100) for name, value, _ in components}
        rec["filter_availability"] = requested_filters_available
        rec["inferred_skills"] = row.get("inferred_skills", [])
        out.append(rec)
    return sorted(out, key=lambda item: (-item["match_percent"], str(item.get("job_title", ""))))[:max(1, min(int(limit), 100))]
