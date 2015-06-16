# This file is part of Indico.
# Copyright (C) 2002 - 2015 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

import sys
from operator import itemgetter

import transaction
from flask import flash, redirect, render_template, request, session
from markupsafe import Markup
from requests.exceptions import HTTPError, Timeout

from indico.core.config import Config
from indico.core.db import db
from indico.modules.auth import Identity, login_user
from indico.modules.bootstrap.forms import BootstrapForm
from indico.modules.cephalopod.util import register_instance
from indico.modules.users import User
from indico.util.i18n import _, get_all_locales, parse_locale
from indico.util.string import to_unicode
from indico.web.flask.util import url_for

import MaKaC
from MaKaC.webinterface.rh.base import RH
from MaKaC.common.info import HelperMaKaCInfo

# TODO: set the time zone here once communities settings are available.


class RHBootstrap(RH):

    def _process_GET(self):
        if User.has_rows:
            return redirect(url_for('misc.index'))
        python_version = sys.version.split()[0]
        return render_template('bootstrap/bootstrap.html',
                               selected_lang_name=parse_locale(session.lang).language_name,
                               language_options=sorted(get_all_locales().items(), key=itemgetter(1)),
                               form=BootstrapForm(language=session.lang),
                               timezone=Config.getInstance().getDefaultTimezone(),
                               indico_version=MaKaC.__version__,
                               python_version=python_version)

    def _process_POST(self):
        if User.has_rows:
            return redirect(url_for('misc.index'))
        setup_form = BootstrapForm(request.form)
        if not setup_form.validate():
            flash(_("Some fields are invalid. Please, correct them and submit the form again."), 'error')
            return redirect(url_for('bootstrap.index'))

        # Creating new user
        user = User()
        user.first_name = to_unicode(setup_form.first_name.data)
        user.last_name = to_unicode(setup_form.last_name.data)
        user.affiliation = to_unicode(setup_form.affiliation.data)
        user.email = to_unicode(setup_form.email.data)
        user.is_admin = True
        user.settings.set('timezone', Config.getInstance().getDefaultTimezone())
        user.settings.set('lang', to_unicode(setup_form.language.data))

        identity = Identity(provider='indico', identifier=setup_form.username.data, password=setup_form.password.data)
        user.identities.add(identity)
        full_name = user.full_name  # needed after the session closes

        login_user(user, identity)
        db.session.add(user)
        transaction.commit()

        # Configuring server's settings
        minfo = HelperMaKaCInfo.getMaKaCInfoInstance()
        minfo.setOrganisation(setup_form.affiliation.data)
        minfo.setLang(setup_form.language.data)

        flash(Markup(
            _("Congrats {name}, Indico is now ready and you are logged in with your new administration account!<br>"
              "Don't forget to tweak <a href=\"{settings_link}\">Indico's settings</a> and update your "
              "<a href=\"{profile_link}\">profile</a>.").format(
                name=full_name, settings_link=url_for('admin.adminList'), profile_link=url_for('users.user_dashboard'))
        ), 'success')

        # Activate instance tracking
        if setup_form.enable_tracking.data:
            contact_name = setup_form.contact_name.data
            contact_email = setup_form.contact_email.data

            try:
                register_instance(contact_name, contact_email)
            except (HTTPError, ValueError) as err:
                flash(Markup(_("Instance tracking registration failed with: {err.message}.<br>"
                               "See the logs for details and try again <a href=\"{link}\">here</a>.").format(
                                   link=url_for('cephalopod.index'), err=err)), 'error')
            except Timeout:
                flash(Markup(_("Instance tracking registration timed-out. Please try again in a while "
                               "<a href=\"{link}\">here</a>.").format(link=url_for('cephalopod.index'))), 'error')
            else:
                flash(Markup(_("Welcome to the Indico community, your server has been registered!<br>You can manage it "
                               "<a href=\"{link}\">here</a>.").format(link=url_for('cephalopod.index'))), 'success')

        return redirect(url_for('misc.index'))
