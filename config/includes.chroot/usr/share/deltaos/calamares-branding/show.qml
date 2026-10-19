import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation {
    id: presentation

    Timer {
        interval: 9000
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }

    Slide {
        Rectangle {
            anchors.fill: parent
            radius: 14
            color: "#111a31"
        }
        Column {
            anchors.centerIn: parent
            width: parent.width * 0.78
            spacing: 18
            Text {
                text: "Welcome to DeltaOS"
                color: "#f2f5ff"
                font.pixelSize: 28
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                width: parent.width
            }
            Text {
                text: "A clear, capable desktop for study, games, and everyday work."
                color: "#b7c5e4"
                font.pixelSize: 18
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                width: parent.width
            }
        }
    }

    Slide {
        Rectangle {
            anchors.fill: parent
            radius: 14
            color: "#111a31"
        }
        Column {
            anchors.centerIn: parent
            width: parent.width * 0.78
            spacing: 18
            Text {
                text: "Made for your everyday work"
                color: "#f2f5ff"
                font.pixelSize: 28
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                width: parent.width
            }
            Text {
                text: "Use Firefox, LibreOffice, KDE apps, and a growing collection of open-source tools."
                color: "#b7c5e4"
                font.pixelSize: 18
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                width: parent.width
            }
        }
    }

    Slide {
        Rectangle {
            anchors.fill: parent
            radius: 14
            color: "#111a31"
        }
        Column {
            anchors.centerIn: parent
            width: parent.width * 0.78
            spacing: 18
            Text {
                text: "Try games and more apps"
                color: "#f2f5ff"
                font.pixelSize: 28
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                width: parent.width
            }
            Text {
                text: "Steam, Lutris, Wine, and optional Waydroid support help you explore more software. Compatibility depends on each app and your hardware."
                color: "#b7c5e4"
                font.pixelSize: 18
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                width: parent.width
            }
        }
    }
}
