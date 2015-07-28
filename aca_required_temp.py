
import numpy as np

import agasc
from Chandra.Time import DateTime
import Ska.Sun
from Ska.quatutil import radec2yagzag
from Quaternion import Quat
import chandra_aca
from starcheck.star_probs import t_ccd_warm_limit
from astropy.table import Table

N_ACQ_STARS = 5
EDGE_DIST = 30
COLD_T_CCD = -21
WARM_T_CCD = -10

ROLL_TABLE = Table.read('roll_limits.dat', format='ascii')

# Save temperature calc a combination of stars
# indexed by hash of agasc ids
T_CCD_CACHE = {}


def get_options():
    import argparse
    parser = argparse.ArgumentParser(
        description="Get required ACA temp for an attitude over a cycle")
    parser.add_argument("ra",
                        type=float)
    parser.add_argument("dec",
                        type=float)
    parser.add_argument("--out",
                        default="roll_temps.dat")
    parser.add_argument("--start",
                        default="2014-09-01")
    parser.add_argument("--stop",
                        default="2015-12-31")
    opt = parser.parse_args()
    return opt


def select_stars(ra, dec, roll, cone_stars):

    cols = ['AGASC_ID', 'MAG_ACA', 'COLOR1',
            'RA_PMCORR', 'DEC_PMCORR']
    ok_cone_stars = cone_stars[
        (cone_stars['MAG_ACA'] < 10.8) &
        (cone_stars['CLASS'] == 0) &
        (cone_stars['ASPQ1'] == 0) &
        (cone_stars['COLOR1'] != 0.7)][cols]
    ok_cone_stars.sort('MAG_ACA')

    q = Quat((ra, dec, roll))
    yag, zag = radec2yagzag(ok_cone_stars['RA_PMCORR'], ok_cone_stars['DEC_PMCORR'], q)
    row, col = chandra_aca.yagzag_to_pixels(yag * 3600,
                                            zag * 3600, allow_bad=True)
    edgepad = EDGE_DIST / 5.
    stars_in_fov = ok_cone_stars[
        (row < (512 - edgepad)) &
        (row > (-512 + edgepad)) &
        (col < (512 - edgepad)) &
        (col > (-512 + edgepad))]

    return stars_in_fov[0:8]


def max_temp(ra, dec, roll, time, cone_stars):
    stars = select_stars(ra, dec, roll, cone_stars)
    id_hash = tuple(stars['AGASC_ID'])
    if id_hash not in T_CCD_CACHE:
        # Get tuple of (t_ccd, n_acq) for this star field and cache
        T_CCD_CACHE[id_hash] = t_ccd_warm_limit(
            date=time,
            mags=stars['MAG_ACA'],
            colors=stars['COLOR1'],
            min_n_acq=N_ACQ_STARS,
            cold_t_ccd=COLD_T_CCD,
            warm_t_ccd=WARM_T_CCD)
    return T_CCD_CACHE[id_hash]


def get_rolldev(pitch):
    idx = np.searchsorted(ROLL_TABLE['pitch'], pitch, side='right')
    return ROLL_TABLE['rolldev'][idx - 1]


def get_t_ccd_roll(ra, dec, pitch, time, cone_stars):
    """
    Loop over possible roll range for this pitch and return best
    and nominal temperature/roll combinations
    """
    best_roll = None
    best_t_ccd = None
    nom_roll = Ska.Sun.nominal_roll(ra, dec, time=time)
    nom_t_ccd, nom_n_acq = max_temp(ra, dec, nom_roll, time=time, cone_stars=cone_stars)
    # check off nominal rolls in allowed range for a better catalog / temperature
    roll_dev = get_rolldev(pitch)
    d_roll = 1.0
    plus_minus_rolls = np.concatenate([[-r, r] for r in
                                       np.arange(d_roll, roll_dev, d_roll)])
    off_nom_rolls = nom_roll + plus_minus_rolls
    for roll in off_nom_rolls:
        roll_t_ccd, roll_n_acq = max_temp(ra, dec, roll, time=time, cone_stars=cone_stars)
        if roll_t_ccd is not None:
            if best_t_ccd is None or roll_t_ccd > best_t_ccd:
                best_t_ccd = roll_t_ccd
                best_roll = roll
            if best_t_ccd == WARM_T_CCD:
                break
    return nom_t_ccd, nom_roll, best_t_ccd, best_roll


def t_ccd_for_attitude(ra, dec, start='2014-09-01', stop='2015-12-31'):
    # reset the caches at every new attitude
    global T_CCD_CACHE
    T_CCD_CACHE.clear()


    start = DateTime(start)
    stop = DateTime(stop)

    # set the agasc proper motion time to be in the middle of the
    # requested cycle
    lts_mid_time = start + (stop - start) / 2

    # Get stars in this field
    cone_stars = agasc.get_agasc_cone(ra, dec, date=lts_mid_time)

    # get a list of days
    days = start + np.arange(stop - start)

    temps = {}
    # loop over them
    for day in days.date:
        day_pitch = Ska.Sun.pitch(ra, dec, time=day)
        if day_pitch < 46.4 or day_pitch > 170:
            continue
        nom_t_ccd, nom_roll, best_t_ccd, best_roll = get_t_ccd_roll(
            ra, dec, day_pitch, time=day, cone_stars=cone_stars)
        temps["{}".format(day[0:8])] = {
            'day': day,
            'pitch': day_pitch,
            'nom_roll': nom_roll,
            'nom_t_ccd': nom_t_ccd,
            'best_roll': best_roll,
            'best_t_ccd': best_t_ccd}

    t_ccd_table = Table(temps.values())['day', 'pitch',
                                        'nom_roll', 'nom_t_ccd',
                                        'best_roll', 'best_t_ccd']
    t_ccd_table['pitch'].format = '.2f'
    t_ccd_table['nom_roll'].format = '.2f'
    t_ccd_table['nom_t_ccd'].format = '.2f'
    t_ccd_table['best_roll'].format = '.2f'
    t_ccd_table['best_t_ccd'].format = '.2f'
    t_ccd_table.sort('day')
    return t_ccd_table


def main():
    """
    Determine required ACA temperature for an attitude over a time range
    """
    opt = get_options()
    temp_table = temps_for_attitude(opt.ra, opt.dec,
                                    start=opt.start,
                                    stop=opt.stop)
    temp_table.write(opt.out, format='ascii.fixed_width_two_line')

if __name__ == '__main__':
    main()





