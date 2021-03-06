from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic.detail import DetailView
from django.views.generic import FormView
from django import forms
from django.http import Http404
from datetime import datetime
import json

from observe.schedule import format_request, submit_scheduler_api
from observe.images import check_request_api, download_frames, find_frames, get_thumbnails
from observe.models import Asteroid, Observation
import logging

logger = logging.getLogger('asteroid')
state_options = {'PENDING' : 'P', 'COMPLETED' :'C', 'CANCELED':'N', 'FAILED':'F', 'UNSCHEDULABLE':'F'}


def home(request):
    asteroids = Asteroid.objects.all().order_by('-end')
    return render(request,
                'observe/home.html',
                {'asteroids_past':asteroids.filter(active=False),
                'asteroids_active':asteroids.filter(active=True)})

class EmailForm(forms.Form):
    user_name = forms.CharField()

class ObservationView(DetailView):
    """
    View observations on LCOGT
    """
    model = Observation
    template_name = 'observe/observation.html'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(ObservationView, self).get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        fids = self.object.frame_ids
        if fids:
            frame_ids = [{'id':f} for f in json.loads(fids)]
            context['frames'] = get_thumbnails(frame_ids)
        return context

class AsteroidView(DetailView):
    """
    Schedule observations on LCOGT given a full set of observing parameters
    """
    model = Asteroid
    template_name = 'observe/asteroid.html'

class AsteroidSchedule(FormView):
    success_url = reverse_lazy('home')
    form_class = EmailForm

    def post(self, request, *args, **kwargs):
        try:
            body = Asteroid.objects.get(pk=kwargs['pk'])
            self.body = body
            return super(AsteroidSchedule, self).post(request, *args, **kwargs)
        except Asteroid.DoesNotExist:
            raise Http404("Asteroid does not exist")

    def form_valid(self, form):
        try:
            req = Observation.objects.get(asteroid=self.body, email=form.cleaned_data['user_name'])
        except Observation.DoesNotExist:
            resp = send_request(self.body, form.cleaned_data)
            messages.add_message(self.request, resp['code'] , resp['msg'])
            return super(AsteroidSchedule, self).form_valid(form)

        messages.info(self.request,"Checking status of your %s observations" % self.body.name)
        return redirect('request_detail', pk=req.id)


def update_status(req):
    if not req.request_ids:
        logger.debug("Finding request IDs for {}".format(req))
        status = check_request_api(req.track_num)
        if not status:
            return False
        logger.debug(status['requests'][0]['windows'][0]['end'])
        req.status = state_options.get(status['state'],'U')
        request_ids = [r['id'] for r in status['requests']]
        req.request_ids = json.dumps(request_ids)
        req.save()
    if not req.frame_ids:
        logger.debug("Finding frame IDs for {}".format(req))
        if req.request_ids:
            frames = find_frames(json.loads(req.request_ids), last_update=req.asteroid.last_update)
        req.frame_ids = json.dumps(frames)
        logger.debug(frames)
        if len(frames) == req.asteroid.exposure_count:
            req.status = 'C'
            req.update = datetime.utcnow()
            req.save()
            return True
    return False

def send_request(asteroid, form):
    obs_params = format_request(asteroid)
    resp_status, resp_msg = submit_scheduler_api(obs_params)
    if resp_status:
        reqids = [_['id'] for _ in resp_msg['requests']]
        req_params = {
            'track_num' : resp_msg['id'],
            'status'    : 'P',
            'email'     : form['user_name'],
            'asteroid'  : asteroid,
            'request_ids' : json.dumps(reqids)
        }
        r = Observation(**req_params)
        r.save()
        msg = "Observations submitted successfully"
        code = messages.SUCCESS
        logger.debug('Saved request %s' % r)
    else:
        msg = 'Observation not scheduled: %s' % resp_msg
        logger.error(resp_msg)
        code = messages.ERROR
    return {'status':None, 'msg': msg,'code':code}
