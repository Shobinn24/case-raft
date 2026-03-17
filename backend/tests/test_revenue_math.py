"""Test revenue by practice area math with fake bill data."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.firm_data import RevenueByPracticeArea


def make_bill(number, issued_at, state, total, paid, balance, practice_area):
    """Create a fake bill dict matching Clio API structure."""
    return {
        "id": int(number),
        "number": str(number),
        "issued_at": issued_at,
        "due_at": issued_at,  # simplify
        "state": state,
        "total": total,
        "sub_total": total,
        "balance": balance,
        "paid": paid,
        "paid_at": "2026-03-15" if state == "paid" else None,
        "matters": [
            {
                "id": 1,
                "display_number": f"M-{number}",
                "practice_area": {"name": practice_area},
            }
        ],
    }


# Reference date: 2026-03-16 (today)
REF_DATE = "2026-03-16"

# Build test bills with known values
FAKE_BILLS = [
    # --- PAID bills (for "collected" mode) ---
    # Family Law: issued 10 days ago (1-30 bucket), paid $1,000
    make_bill(1, "2026-03-06", "paid", 1000, 1000, 0, "Family Law"),
    # Family Law: issued 45 days ago (31-60 bucket), paid $2,000
    make_bill(2, "2026-01-30", "paid", 2000, 2000, 0, "Family Law"),
    # Criminal Law: issued 5 days ago (1-30 bucket), paid $500
    make_bill(3, "2026-03-11", "paid", 500, 500, 0, "Criminal Law"),
    # Criminal Law: issued 80 days ago (61-90 bucket), paid $3,000
    make_bill(4, "2025-12-26", "paid", 3000, 3000, 0, "Criminal Law"),
    # Real Estate: issued 100 days ago (91+ bucket), paid $5,000
    make_bill(5, "2025-12-06", "paid", 5000, 5000, 0, "Real Estate"),

    # --- UNPAID bills (for "outstanding" mode) ---
    # Family Law: issued 20 days ago (1-30 bucket), $800 outstanding
    make_bill(6, "2026-02-24", "awaiting_payment", 800, 0, 800, "Family Law"),
    # Criminal Law: issued 50 days ago (31-60 bucket), $1,500 outstanding
    make_bill(7, "2026-01-25", "awaiting_payment", 1500, 0, 1500, "Criminal Law"),
    # Real Estate: issued 95 days ago (91+ bucket), $2,200 outstanding
    make_bill(8, "2025-12-12", "awaiting_payment", 2200, 0, 2200, "Real Estate"),
    # Partial payment: Family Law, issued 70 days ago (61-90), $600 of $1000 outstanding
    make_bill(9, "2026-01-05", "awaiting_payment", 1000, 400, 600, "Family Law"),
]


def test_collected_mode():
    print("=" * 60)
    print("COLLECTED REVENUE (Paid) MODE")
    print("=" * 60)

    rev = RevenueByPracticeArea(FAKE_BILLS, REF_DATE, mode="collected")

    print(f"\nReference date: {REF_DATE}")
    print(f"Mode: {rev.mode}")
    print()

    # Print table
    header = f"{'Practice Area':<20} {'1-30':>10} {'31-60':>10} {'61-90':>10} {'91+':>10} {'Total':>12}"
    print(header)
    print("-" * len(header))

    for row in rev.rows:
        print(
            f"{row['practice_area']:<20} "
            f"${row['1_30']:>9,.2f} "
            f"${row['31_60']:>9,.2f} "
            f"${row['61_90']:>9,.2f} "
            f"${row['91_plus']:>9,.2f} "
            f"${row['total']:>11,.2f}"
        )

    ct = rev.column_totals
    print("-" * len(header))
    print(
        f"{'TOTAL':<20} "
        f"${ct['1_30']:>9,.2f} "
        f"${ct['31_60']:>9,.2f} "
        f"${ct['61_90']:>9,.2f} "
        f"${ct['91_plus']:>9,.2f} "
        f"${ct['total']:>11,.2f}"
    )

    # Verify expected values
    print("\n--- EXPECTED ---")
    print("Criminal Law:  1-30=$500, 61-90=$3,000, total=$3,500")
    print("Family Law:    1-30=$1,000, 31-60=$2,000, total=$3,000")
    print("Real Estate:   91+=$5,000, total=$5,000")
    print("GRAND TOTAL:   $11,500")

    # Assertions
    errors = []

    # Criminal Law
    crim = next((r for r in rev.rows if r["practice_area"] == "Criminal Law"), None)
    if crim:
        if crim["1_30"] != 500: errors.append(f"Criminal 1-30: expected 500, got {crim['1_30']}")
        if crim["31_60"] != 0: errors.append(f"Criminal 31-60: expected 0, got {crim['31_60']}")
        if crim["61_90"] != 3000: errors.append(f"Criminal 61-90: expected 3000, got {crim['61_90']}")
        if crim["91_plus"] != 0: errors.append(f"Criminal 91+: expected 0, got {crim['91_plus']}")
        if crim["total"] != 3500: errors.append(f"Criminal total: expected 3500, got {crim['total']}")
    else:
        errors.append("Criminal Law row missing!")

    # Family Law
    fam = next((r for r in rev.rows if r["practice_area"] == "Family Law"), None)
    if fam:
        if fam["1_30"] != 1000: errors.append(f"Family 1-30: expected 1000, got {fam['1_30']}")
        if fam["31_60"] != 2000: errors.append(f"Family 31-60: expected 2000, got {fam['31_60']}")
        if fam["61_90"] != 0: errors.append(f"Family 61-90: expected 0, got {fam['61_90']}")
        if fam["total"] != 3000: errors.append(f"Family total: expected 3000, got {fam['total']}")
    else:
        errors.append("Family Law row missing!")

    # Real Estate
    re_ = next((r for r in rev.rows if r["practice_area"] == "Real Estate"), None)
    if re_:
        if re_["91_plus"] != 5000: errors.append(f"RealEstate 91+: expected 5000, got {re_['91_plus']}")
        if re_["total"] != 5000: errors.append(f"RealEstate total: expected 5000, got {re_['total']}")
    else:
        errors.append("Real Estate row missing!")

    # Grand total
    if ct["total"] != 11500: errors.append(f"Grand total: expected 11500, got {ct['total']}")

    if errors:
        print("\n❌ ERRORS:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n✅ All collected revenue checks passed!")

    return errors


def test_outstanding_mode():
    print("\n" + "=" * 60)
    print("OUTSTANDING AR (Unpaid) MODE")
    print("=" * 60)

    rev = RevenueByPracticeArea(FAKE_BILLS, REF_DATE, mode="outstanding")

    print(f"\nReference date: {REF_DATE}")
    print(f"Mode: {rev.mode}")
    print()

    header = f"{'Practice Area':<20} {'1-30':>10} {'31-60':>10} {'61-90':>10} {'91+':>10} {'Total':>12}"
    print(header)
    print("-" * len(header))

    for row in rev.rows:
        print(
            f"{row['practice_area']:<20} "
            f"${row['1_30']:>9,.2f} "
            f"${row['31_60']:>9,.2f} "
            f"${row['61_90']:>9,.2f} "
            f"${row['91_plus']:>9,.2f} "
            f"${row['total']:>11,.2f}"
        )

    ct = rev.column_totals
    print("-" * len(header))
    print(
        f"{'TOTAL':<20} "
        f"${ct['1_30']:>9,.2f} "
        f"${ct['31_60']:>9,.2f} "
        f"${ct['61_90']:>9,.2f} "
        f"${ct['91_plus']:>9,.2f} "
        f"${ct['total']:>11,.2f}"
    )

    print("\n--- EXPECTED ---")
    print("Criminal Law:  31-60=$1,500, total=$1,500")
    print("Family Law:    1-30=$800, 61-90=$600, total=$1,400")
    print("Real Estate:   91+=$2,200, total=$2,200")
    print("GRAND TOTAL:   $5,100")

    errors = []

    # Criminal Law
    crim = next((r for r in rev.rows if r["practice_area"] == "Criminal Law"), None)
    if crim:
        if crim["31_60"] != 1500: errors.append(f"Criminal 31-60: expected 1500, got {crim['31_60']}")
        if crim["total"] != 1500: errors.append(f"Criminal total: expected 1500, got {crim['total']}")
    else:
        errors.append("Criminal Law row missing!")

    # Family Law
    fam = next((r for r in rev.rows if r["practice_area"] == "Family Law"), None)
    if fam:
        if fam["1_30"] != 800: errors.append(f"Family 1-30: expected 800, got {fam['1_30']}")
        if fam["61_90"] != 600: errors.append(f"Family 61-90: expected 600, got {fam['61_90']}")
        if fam["total"] != 1400: errors.append(f"Family total: expected 1400, got {fam['total']}")
    else:
        errors.append("Family Law row missing!")

    # Real Estate
    re_ = next((r for r in rev.rows if r["practice_area"] == "Real Estate"), None)
    if re_:
        if re_["91_plus"] != 2200: errors.append(f"RealEstate 91+: expected 2200, got {re_['91_plus']}")
        if re_["total"] != 2200: errors.append(f"RealEstate total: expected 2200, got {re_['total']}")
    else:
        errors.append("Real Estate row missing!")

    if ct["total"] != 5100: errors.append(f"Grand total: expected 5100, got {ct['total']}")

    if errors:
        print("\n❌ ERRORS:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n✅ All outstanding AR checks passed!")

    return errors


def test_clio_style_id_only():
    """Test with Clio-style data where practice_area only has id (no name).
    This simulates what actually comes back from the API due to
    second-level nesting limitations.
    """
    print("\n" + "=" * 60)
    print("CLIO-STYLE (practice_area has id only, using lookup)")
    print("=" * 60)

    # Bills with practice_area as id-only (what Clio actually returns)
    clio_bills = [
        {
            "id": 1, "number": "1", "issued_at": "2026-03-06",
            "state": "paid", "total": 1000, "paid": 1000, "balance": 0,
            "matters": [{"id": 10, "practice_area": {"id": 101}}],
        },
        {
            "id": 2, "number": "2", "issued_at": "2026-01-30",
            "state": "paid", "total": 2000, "paid": 2000, "balance": 0,
            "matters": [{"id": 11, "practice_area": {"id": 102}}],
        },
        {
            "id": 3, "number": "3", "issued_at": "2026-03-11",
            "state": "paid", "total": 500, "paid": 500, "balance": 0,
            "matters": [{"id": 12, "practice_area": {"id": 101}}],
        },
    ]

    # Practice area lookup (from separate /practice_areas.json call)
    pa_lookup = {101: "Family Law", 102: "Criminal Law"}

    rev = RevenueByPracticeArea(clio_bills, REF_DATE, mode="collected",
                                 practice_area_lookup=pa_lookup)

    errors = []

    print(f"\nRows: {len(rev.rows)}")
    for row in rev.rows:
        print(f"  {row['practice_area']}: total=${row['total']:,.2f}")

    # Family Law should have bills 1 ($1000) and 3 ($500) = $1,500
    fam = next((r for r in rev.rows if r["practice_area"] == "Family Law"), None)
    if fam:
        if fam["total"] != 1500:
            errors.append(f"Family total: expected 1500, got {fam['total']}")
    else:
        errors.append("Family Law row missing — lookup failed!")

    # Criminal Law should have bill 2 ($2000)
    crim = next((r for r in rev.rows if r["practice_area"] == "Criminal Law"), None)
    if crim:
        if crim["total"] != 2000:
            errors.append(f"Criminal total: expected 2000, got {crim['total']}")
    else:
        errors.append("Criminal Law row missing — lookup failed!")

    # Should NOT have "Uncategorized"
    uncat = next((r for r in rev.rows if r["practice_area"] == "Uncategorized"), None)
    if uncat:
        errors.append(f"Uncategorized found with ${uncat['total']} — lookup not working!")

    if errors:
        print("\n❌ ERRORS:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n✅ Clio-style id-only lookup passed!")

    return errors


if __name__ == "__main__":
    all_errors = []
    all_errors.extend(test_collected_mode())
    all_errors.extend(test_outstanding_mode())
    all_errors.extend(test_clio_style_id_only())

    print("\n" + "=" * 60)
    if all_errors:
        print(f"FAILED — {len(all_errors)} error(s) found")
    else:
        print("ALL TESTS PASSED ✅")
    print("=" * 60)
