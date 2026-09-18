pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.PREFER_SETTINGS)
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://storage.googleapis.com/download.flutter.io") }
    }
}
rootProject.name = "ChessScan"
include(":app")

// 集成 Flutter module (FEN 编辑器)
apply(from = "../flutter_editor/.android/include_flutter.groovy")
