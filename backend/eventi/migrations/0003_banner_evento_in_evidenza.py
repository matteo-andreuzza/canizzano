"""
Il banner della home smette di essere «della sagra»: la redazione ne sceglie
anche destinazione ed etichetta del bottone, cosi' lo stesso spazio annuncia
la sagra, le iscrizioni al Grest o quelle al catechismo.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventi', '0002_articoli_album_foto_esterne'),
    ]

    operations = [
        migrations.AddField(
            model_name='impostazionisito',
            name='banner_collegamento',
            field=models.CharField(
                blank=True,
                help_text=(
                    'Dove porta il bottone: un indirizzo del sito (/grest, /calendario, '
                    '/eventi/<slug>) oppure un link esterno completo di https://. '
                    'Se resta vuoto porta alla pagina della sagra.'
                ),
                max_length=200,
                verbose_name='collegamento del bottone',
            ),
        ),
        migrations.AddField(
            model_name='impostazionisito',
            name='banner_etichetta_bottone',
            field=models.CharField(
                blank=True,
                help_text='Se resta vuoto il bottone dice «Vai al programma».',
                max_length=40,
                verbose_name='testo del bottone',
            ),
        ),
        migrations.AlterField(
            model_name='impostazionisito',
            name='mostra_banner_sagra',
            field=models.BooleanField(default=True, verbose_name='mostra il banner in home'),
        ),
        migrations.AlterField(
            model_name='impostazionisito',
            name='banner_occhiello',
            field=models.CharField(
                blank=True,
                default='Sta arrivando',
                help_text='La riga piccola sopra il titolo: «Sta arrivando», «Iscrizioni aperte»…',
                max_length=60,
                verbose_name='occhiello',
            ),
        ),
        migrations.AlterField(
            model_name='impostazionisito',
            name='banner_titolo',
            field=models.CharField(
                blank=True,
                default='Canizzano in Festa · 2 → 11 ottobre',
                help_text='Se resta vuoto il banner non compare, anche se acceso.',
                max_length=160,
                verbose_name='titolo',
            ),
        ),
        migrations.AlterField(
            model_name='impostazionisito',
            name='banner_testo',
            field=models.CharField(
                blank=True,
                help_text='Una riga di dettaglio sotto il titolo. Facoltativa.',
                max_length=280,
                verbose_name='testo',
            ),
        ),
    ]
