/* DeltaOS installer slideshow.
 *
 * Structure copied from Debian's own live installer slideshow, which is known
 * to load with the Calamares version shipped in Debian 13 (slideshowAPI 2):
 * one Presentation, a repeating Timer, and Slides holding explicitly sized
 * items. Fixed sizes matter: a Slide is a bare Item, so child items that only
 * anchor to the parent would collapse when the presentation resizes itself.
 */
import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation
{
    id: presentation

    Timer {
        interval: 9000
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }

    Slide {
        Image {
            id: welcomeImage
            source: "deltaos-welcome.png"
            width: 467; height: 146
            fillMode: Image.PreserveAspectFit
            anchors.centerIn: parent
        }
        Text {
            anchors.horizontalCenter: welcomeImage.horizontalCenter
            anchors.top: welcomeImage.bottom
            anchors.topMargin: 18
            width: 520
            text: qsTr("Welcome to DeltaOS.<br/>" +
                       "The rest of the installation runs automatically and should finish in a few minutes.")
            color: "#dce5ff"
            font.pixelSize: 16
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Slide {
        Text {
            anchors.centerIn: parent
            width: 540
            text: qsTr("One desktop for study, work and play.<br/><br/>" +
                       "Firefox, LibreOffice, KDE applications and the DeltaOS hub are ready after the first boot.")
            color: "#dce5ff"
            font.pixelSize: 18
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Slide {
        Text {
            anchors.centerIn: parent
            width: 540
            text: qsTr("Windows and Android applications.<br/><br/>" +
                       "Wine runs many Windows programs and Waydroid can run Android apps when your hardware supports it. Compatibility depends on the application.")
            color: "#dce5ff"
            font.pixelSize: 18
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
