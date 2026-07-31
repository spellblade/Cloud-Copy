from app.services.pikpak_client import next_available_name, split_filename


def test_split_filename():
    assert split_filename("Misumi Walkthrough v0.7.pdf") == (
        "Misumi Walkthrough v0.7",
        ".pdf",
    )
    assert split_filename("noext") == ("noext", "")


def test_next_available_free():
    assert next_available_name("a.pdf", set()) == "a.pdf"
    assert next_available_name("a.pdf", {"b.pdf"}) == "a.pdf"


def test_next_available_collision():
    taken = {"Misumi Walkthrough v0.7.pdf"}
    assert (
        next_available_name("Misumi Walkthrough v0.7.pdf", taken)
        == "Misumi Walkthrough v0.7(1).pdf"
    )
    taken.add("Misumi Walkthrough v0.7(1).pdf")
    assert (
        next_available_name("Misumi Walkthrough v0.7.pdf", taken)
        == "Misumi Walkthrough v0.7(2).pdf"
    )
