apps += NativeApps::App
app_headers += apps/native_apps/app.h
apps_src += apps/native_apps/app.cpp
i18n_files += apps/native_apps/base.universal.i18n

# The launcher shares SettingsIcon. Generate its header before compiling this
# consumer too; the settings app's dependency does not order parallel builds.
$(call object_for,apps/native_apps/app.cpp): $(call object_for,apps/settings/settings_icon.png)
