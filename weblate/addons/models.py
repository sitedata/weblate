# -*- coding: utf-8 -*-
#
# Copyright © 2012 - 2018 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate <https://weblate.org/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

from __future__ import unicode_literals

from appconf import AppConf

from django.db import models
from django.dispatch import receiver
from django.utils.functional import cached_property

from weblate.addons.events import (
    EVENT_CHOICES, EVENT_POST_PUSH, EVENT_POST_UPDATE, EVENT_PRE_COMMIT,
    EVENT_POST_COMMIT, EVENT_POST_ADD,
)

from weblate.trans.models import SubProject
from weblate.trans.signals import (
    vcs_post_push, vcs_post_update, vcs_pre_commit, vcs_post_commit,
    translation_post_add,
)
from weblate.utils.classloader import ClassLoader
from weblate.utils.fields import JSONField

# Initialize addons registry
ADDONS = ClassLoader('WEBLATE_ADDONS', False)


class AddonQuerySet(models.QuerySet):
    def filter_event(self, component, event):
        return self.filter(
            component=component,
            event__event=event
        )


class Addon(models.Model):
    component = models.ForeignKey(SubProject)
    name = models.CharField(max_length=100)
    configuration = JSONField()
    state = JSONField()

    objects = AddonQuerySet.as_manager()

    class Meta(object):
        unique_together = ('component', 'name')

    def configure_events(self, events):
        for event in events:
            Event.objects.get_or_create(addon=self, event=event)
        self.event_set.exclude(event__in=events).delete()

    @cached_property
    def addon(self):
        return ADDONS[self.name](self)


class Event(models.Model):
    addon = models.ForeignKey(Addon)
    event = models.IntegerField(choices=EVENT_CHOICES)

    class Meta(object):
        unique_together = ('addon', 'event')


class AddonsConf(AppConf):
    ADDONS = (
        'weblate.addons.gettext.GenerateMoAddon',
        'weblate.addons.gettext.UpdateLinguasAddon',
        'weblate.addons.gettext.UpdateConfigureAddon',
        'weblate.addons.gettext.MsgmergeAddon',
    )

    class Meta(object):
        prefix = 'WEBLATE'


@receiver(vcs_post_push)
def post_push(sender, component, **kwargs):
    for addon in Addon.objects.filter_event(component, EVENT_POST_PUSH):
        addon.addon.post_push(component)


@receiver(vcs_post_update)
def post_update(sender, component, previous_head, **kwargs):
    for addon in Addon.objects.filter_event(component, EVENT_POST_UPDATE):
        addon.addon.post_update(component, previous_head)


@receiver(vcs_pre_commit)
def pre_commit(sender, translation, **kwargs):
    addons = Addon.objects.filter_event(
        translation.subproject, EVENT_PRE_COMMIT
    )
    for addon in addons:
        addon.addon.pre_commit(translation)


@receiver(vcs_post_commit)
def post_commit(sender, translation, **kwargs):
    addons = Addon.objects.filter_event(
        translation.subproject, EVENT_POST_COMMIT
    )
    for addon in addons:
        addon.addon.post_commit(translation)


@receiver(translation_post_add)
def post_add(sender, translation, **kwargs):
    addons = Addon.objects.filter_event(
        translation.subproject, EVENT_POST_ADD
    )
    for addon in addons:
        addon.addon.post_add(translation)
