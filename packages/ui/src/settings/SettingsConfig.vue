<script setup lang="ts">
  import { RefreshOutline } from '@vicons/ionicons5'
  import { SETTING_GROUPS, SETTING_SLIDERS } from '@virtual-tcu/shared/config/settings'
  import { NButton, NCard, NFlex, NIcon, NText, NSlider, useDialog } from 'naive-ui'
  import { computed, inject } from 'vue'
  import { settingsContextKey } from './context'
  import FeatureToggleList from './FeatureToggleList.vue'

  const ctx = inject(settingsContextKey)!
  const { t, store, featureToggles, configNumber, configBool, sliderUnit } = ctx
  const dialog = useDialog()

  // Render the sliders grouped by drive mode. Without the group headings the
  // four "WOT upshift" sliders (Comfort / Sport-curve / Race / Offroad) all
  // carry the same label, so it is impossible to tell which one is in effect.
  const sliderByKey = computed(() => new Map(SETTING_SLIDERS.map((s) => [s.key, s])))
  const groupedSliders = computed(() =>
    SETTING_GROUPS.map((g) => ({
      i18nKey: g.i18nKey,
      hintKey: g.hintKey,
      sliders: g.keys
        .map((k) => sliderByKey.value.get(k))
        .filter((s): s is NonNullable<typeof s> => Boolean(s)),
    })).filter((g) => g.sliders.length > 0),
  )

  function resetConfig() {
    dialog.warning({
      title: t('settings.reset'),
      content: t('settings.resetConfirm'),
      positiveText: t('modal.confirm'),
      negativeText: t('modal.cancel'),
      onPositiveClick: () => store.resetConfig(),
    })
  }
</script>

<template>
  <NFlex vertical :size="16">
    <NCard :title="t('settings.features')" size="small" :bordered="false">
      <FeatureToggleList
        :toggles="featureToggles"
        :config-bool="configBool"
        @set-config="(key, v) => store.setConfig(key, v)"
      />
    </NCard>

    <NCard :title="t('settings.title')" size="small" :bordered="false">
      <NFlex vertical :size="18">
        <div v-for="g in groupedSliders" :key="g.i18nKey">
          <NText strong style="font-size: 13px">
            {{ t(`settings.${g.i18nKey}`) }}
          </NText>
          <NFlex vertical :size="12" style="margin-top: 6px">
            <div v-for="s in g.sliders" :key="s.key">
              <NFlex justify="space-between" align="center" style="margin-bottom: 4px">
                <NText>{{ t(`settings.${s.i18nKey}`) }}</NText>
                <NText code style="font-family: ui-monospace, monospace">
                  {{ configNumber(s.key) }}{{ sliderUnit(s) }}
                </NText>
              </NFlex>
              <NSlider
                :value="configNumber(s.key)"
                :min="s.min"
                :max="s.max"
                :step="s.step ?? 1"
                @update:value="(v) => store.setConfig(s.key, v)"
              />
            </div>
          </NFlex>
          <NText
            v-if="g.hintKey"
            depth="3"
            style="display: block; margin-top: 4px; font-size: 12px"
          >
            {{ t(`settings.${g.hintKey}`) }}
          </NText>
        </div>
      </NFlex>
    </NCard>

    <NCard size="small" :bordered="false">
      <NFlex justify="space-between" align="center">
        <NText depth="3" style="font-size: 12px">
          {{ t('settings.autosave') }}
        </NText>
        <NButton type="error" ghost size="small" @click="resetConfig">
          <template #icon>
            <NIcon :component="RefreshOutline" />
          </template>
          {{ t('settings.reset') }}
        </NButton>
      </NFlex>
    </NCard>
  </NFlex>
</template>
