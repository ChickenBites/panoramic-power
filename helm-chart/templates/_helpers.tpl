{{/*
Expand the name of the chart.
*/}}
{{- define "ingestionApi.name" -}}
{{- default .Chart.Name .Values.ingestionApi.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name for Redis.
*/}}
{{- define "redis.fullname" -}}
{{- .Values.redis.fullnameOverride | default "redis" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ingestionApi.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ingestionApi.labels" -}}
helm.sh/chart: {{ include "ingestionApi.chart" . }}
{{ include "ingestionApi.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ingestionApi.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ingestionApi.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Processing Service labels
*/}}
{{- define "processingService.name" -}}
{{- default "processing-service" .Values.processingService.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "processingService.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "processingService.labels" -}}
helm.sh/chart: {{ include "processingService.chart" . }}
{{ include "processingService.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "processingService.selectorLabels" -}}
app.kubernetes.io/name: {{ include "processingService.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Frontend labels
*/}}
{{- define "frontend.name" -}}
{{- default "frontend" .Values.frontend.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "frontend.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "frontend.labels" -}}
helm.sh/chart: {{ include "frontend.chart" . }}
{{ include "frontend.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "frontend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
