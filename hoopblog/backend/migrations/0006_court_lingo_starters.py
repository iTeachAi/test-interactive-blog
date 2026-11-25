from datetime import date

from django.db import migrations


def seed(apps, schema_editor):
    database = schema_editor.connection.alias
    BlogPost = apps.get_model('backend', 'BlogPost')
    CourtTerm = apps.get_model('backend', 'CourtTerm')
    post = BlogPost.objects.using(database).create(
        title='How to ICE a side ball screen',
        slug='how-to-ice-a-side-ball-screen',
        category='Ball-screen defense',
        topics='Pick-and-roll, Team defense',
        summary='See how two defenders keep the ball on one side of the court against a side pick-and-roll.',
        body=(
            'Start on the right wing. The screener approaches from the middle. The on-ball defender calls '
            '“ICE,” takes away the route toward the screen, and sends the dribbler toward the baseline. '
            'The screener’s defender slides below the screen, between the ball and the rim, to contain the drive.\n\n'
            'Walk through it with two offensive players and two defenders. Freeze when the screen is about '
            'to arrive. Check whether the ball handler can still turn toward the middle and whether the second '
            'defender is in position to meet a baseline drive. Repeat on both sides before going live.\n\n'
            'If the screener flips the angle or pops out, communicate early. Ask your coach how your team '
            'wants to handle the pop and who should help on the roll.'
        ),
        status='published',
        date=date(2026, 1, 1),
    )
    post.audiences.set(['player', 'coach', 'parent'])
    term = CourtTerm.objects.using(database).create(
        name='Ice the ball screen',
        slug='ice-the-ball-screen',
        aliases='ICE, down the screen, down coverage, blue coverage, side pick-and-roll coverage',
        meaning='A ball-screen coverage that keeps the dribbler from using a side screen to get toward the middle.',
        when_to_use='A coach or defender calls it when an opponent sets a ball screen on the wing and the defense wants to keep the ball on that side.',
        on_court='The on-ball defender takes away the path to the screen and angles the dribbler toward the baseline. The screener’s defender waits below the screen to contain the drive and protect the rim.',
    )
    term.articles.add(post)
    CourtTerm.objects.using(database).create(
        name='Close out',
        slug='close-out',
        aliases='closeout, closing out',
        meaning='Move from help position toward a player who has just received the ball so you can contest a shot and react to a drive.',
        when_to_use='A coach calls for a closeout when a pass goes to a player the defense has left open.',
        on_court='A defender sprints part of the way toward a shooter on the wing, then shortens their steps, raises a hand and gets balanced enough to slide if the shooter drives.',
    )


class Migration(migrations.Migration):
    dependencies = [('backend', '0005_audience_consultationrequest_blogpost_slug_and_more')]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
