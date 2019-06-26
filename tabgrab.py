from collections import deque

import click
import requests_html


def directive(name, value=None):
    if value is not None:
        return "{%s: %s}" % (name, value)
    return "{%s}" % name


def parse_chords(elems):
    result = ""
    for elem in elems:
        if isinstance(elem, str):
            result += elem
        else:
            result += "[{}]".format(elem.text)
    return result


def intersperse_chords(lyrics, chord_list):
    pos = 0
    last_chord_len = 0
    result = ""
    for spacing, chord in chord_list:
        if pos > len(lyrics):
            result += " " * spacing
        else:
            spacing += last_chord_len
            result += lyrics[pos : pos + spacing]
        result += "[{}]".format(chord)
        pos += spacing
        last_chord_len = len(chord)
    result += lyrics[pos:].rstrip()
    return result


def iter_lines(elements):
    current_line = []
    for element in elements:
        if isinstance(element, str):
            first, *rest = element.split("\n", maxsplit=1)
            current_line.append(first)
            if rest:
                yield current_line
                *rest, last = rest[0].split("\n")
                yield from ([line] for line in rest)
                if last:
                    current_line = [last]
                else:
                    current_line = []
        else:
            current_line.append(element)
    if current_line:
        yield current_line


def is_chord(elem):
    try:
        return elem.tag == "a"
    except Exception:
        return False


def is_comment(elem):
    try:
        return elem.tag == "strong"
    except Exception:
        return False


def line_to_text(elems):
    result = ""
    for e in elems:
        try:
            result += e.text
        except AttributeError:
            result += str(e)
    return result


def create_chordpro(song_url):
    session = requests_html.HTMLSession()
    html = session.get(song_url).html
    header_section = html.find("div.inner-wrap", first=True)
    body = []
    body.append(directive("title", header_section.find("h3", first=True).text))
    body.append(
        directive(
            "artist", header_section.find("a[rel='category tag']", first=True).text
        )
    )
    body.append("")
    content_section = html.find("div#cont > pre", first=True)
    lines = deque(iter_lines(content_section.pq.contents().contents()))

    in_chorus = False
    while lines:
        line = lines.popleft()
        if line and is_comment(line[0]):
            next, *rest = line[1:]
            text = line[0].text_content() + next.split(":")[0]
            body.append(directive("comment", text))
            if "chorus" in text.lower():
                body.append(directive("start_of_chorus"))
                in_chorus = True
            if rest:
                body.append(parse_chords(rest))
            continue

        if any(is_chord(e) for e in line):
            spacing = 0
            chords = []
            for e in line:
                if isinstance(e, str):
                    spacing = len(e)
                else:
                    chords.append((spacing, e.text))
                    spacing = 0
            try:
                next_line = lines.popleft()
            except IndexError:
                next_line = []
            if (
                all(isinstance(e, str) for e in next_line)
                and line_to_text(next_line).strip()
            ):
                body.append(intersperse_chords(line_to_text(next_line), chords))
            else:
                body.append(parse_chords(line))
                lines.appendleft(next_line)
            continue

        text = line_to_text(line)
        if in_chorus and not text.strip():
            body.append(directive("end_of_chorus"))
            in_chorus = False
        body.append(text)

    return "\n".join(body)


@click.group()
def main():
    pass


@main.command()
@click.argument("url")
@click.option("--echo/--no-echo", default=True)
@click.option("--filename")
def song(url, echo, filename=None):
    result = create_chordpro(url)
    if echo:
        print(result)
    if filename:
        with open(filename, "w") as f:
            f.write(result)


@main.command()
@click.argument("username")
@click.argument("password")
def favorites(username, password):
    session = requests_html.HTMLSession()
    resp = session.post(
        "https://ukutabs.com/wp-login.php",
        data={
            "log": username,
            "pwd": password,
            "rememberme": "forever",
            "redirect_to": "https://ukutabs.com/favorites/",
            "wp-submit": "Log in!",
        },
    )
    # TODO: Pagination
    for link in resp.html.find(".archivelist>li>a:first-of-type"):
        url = link.attrs["href"]
        print(url)
        result = create_chordpro(url)
        print(result)


if __name__ == "__main__":
    main()
