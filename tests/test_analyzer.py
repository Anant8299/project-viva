from pathlib import Path

from viva.analyzer import extract_units, interest_score, select_units
from viva.repo import RepoFile, load_from_dir

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "linkshort"


def units_by_name():
    return {u.name: u for u in extract_units(load_from_dir(SAMPLE))}


def test_python_facts():
    u = units_by_name()["create_short_link"]
    assert u.file == "linkshort/shortener.py"
    assert "DuplicateCodeError" in u.catches
    assert "RuntimeError" in u.raises
    assert {"validate_url", "find_by_url", "random_code", "save"} <= set(u.calls)
    assert u.loops == 1
    # exception constructors are not "calls"
    assert "RuntimeError" not in u.calls


def test_branch_outcomes():
    u = units_by_name()["validate_url"]
    assert u.outcomes["not parsed.netloc"] == "raises InvalidURLError"


def test_line_numbers_point_at_def():
    u = units_by_name()["resolve"]
    src = (SAMPLE / "linkshort" / "shortener.py").read_text().splitlines()
    assert src[u.start - 1].startswith("def resolve")
    assert u.source.splitlines()[0].startswith("def resolve")


def test_trivial_units_score_zero():
    assert interest_score(units_by_name()["get"]) == 0


def test_select_spreads_across_files():
    chosen = select_units(extract_units(load_from_dir(SAMPLE)), 5, per_file=2)
    assert len(chosen) == 5
    files = [u.file for u in chosen]
    assert max(files.count(f) for f in set(files)) <= 2


def test_js_units():
    js = RepoFile("src/cart.js", """
export async function checkout(cart, user) {
  if (!user) {
    throw new Error("login");
  }
  try {
    const total = computeTotal(cart);
    return await charge(user, total);
  } catch (err) {
    logFailure(err);
    return null;
  }
}

const computeTotal = (cart) => {
  return cart.items.reduce((s, i) => s + i.price, 0);
};
""")
    units = {u.name: u for u in extract_units([js])}
    assert {"checkout", "computeTotal"} <= set(units)
    co = units["checkout"]
    assert "err" in co.catches or co.catches  # catch(err) captured
    assert {"computeTotal", "charge", "logFailure"} <= set(co.calls)
    assert co.raises == ["Error"]
